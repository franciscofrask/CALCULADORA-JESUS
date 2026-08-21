# -*- coding: utf-8 -*-
"""Arma el HTML del artifact del repaso del 21-08: bloque a bloque, cada cambio con su
captura de la app tal y como queda hoy. Las imagenes van embebidas en base64 (JPEG q50)."""
import base64
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
CAPS = os.path.join(AQUI, "capturas_repaso_2108")
SALIDA = os.path.join(AQUI, "..", "_internos_proceso", "repaso_app_2108.html")

def img(nombre):
    ruta = os.path.join(CAPS, nombre + ".jpg")
    if not os.path.exists(ruta):
        return None
    b64 = base64.b64encode(open(ruta, "rb").read()).decode()
    return f"data:image/jpeg;base64,{b64}"

# ── El contenido, bloque a bloque ────────────────────────────────────────────
# (titulo, intro, [(captura, pie), ...], notas)
BLOQUES = [
    ("07 · Preferencias", """El cliente nuevo marca lo que come en diez cajones con ejemplos,
     confirma sus alimentos a evitar (las alergias llevan candado) y la app le dice en vivo si
     con lo marcado se le puede cuadrar. Sus elecciones y el «cómo quieres tu día» quedan como
     valor por defecto en su ficha.""", [
        ("b07-1-modal-preferencias", "Al entrar por primera vez en Nutrición: los cajones con ejemplos, «Todas / Ninguna» por grupo y el contador de «Guardar · N marcadas»."),
        ("b07-2-alimentos-a-evitar", "La pestaña «Alimentos a evitar (confirmar)» va primero; las alergias del cuestionario salen con candado."),
        ("b07-3-nutricion-tras-guardar", "Guardado: la pantalla de Nutrición queda lista y las preferencias mandan en el sugeridor."),
    ], None),
    ("08 · La guía de suplementación", """La pantalla de Suplementos del cliente ya no es la
     general compuesta: es LA GUÍA de la web, con las 28 fichas literales (¿cuándo?, ¿cuánto?,
     dónde comprarlo con el descuento). Quién ve qué depende del plan.""", [
        ("b08-1-guia-autogestion", "Autogestión (Calculadora): la guía entera, con la oferta del ajuste de 87 € al final."),
        ("b08-2-guia-con-coach", "Con entrenador (Bronze): arriba el aviso de que su plan personalizado llega en unos días; sin oferta."),
    ], None),
    ("09 · Mis macros", """La pestaña solo la ve quien se los calcula. Al que se los pone su
     entrenador no se le enseña un formulario que acabaría en un 403: directamente no tiene la
     entrada, y su histórico vive en Seguimiento → Evolución.""", [
        ("b09-2-nivel1-mis-macros", "El de autogestión: su calculadora y su histórico, con la última y la próxima revisión."),
        ("b09-1-bronze-sin-mis-macros", "El Bronze (con entrenador y macros puestos por él): en su menú no existe «Ajustar macros»."),
    ], """El único matiz a propósito: el recién llegado con coach que aún no tiene macros SÍ ve
     la calculadora, porque el último paso de su alta es «Calcular mis macros» y sin ella se
     quedaba encerrado (pasó con dos personas en producción el 17-08)."""),
    ("10 · Los avisos", """Máximo uno al día y con la entrega por delante. Se añadieron los
     que faltaban (fin de ciclo por fecha, rutina del mes aplazada, «¿Todo bien?» a los 7 días
     de silencio) y las habilitaciones del catálogo mandan sobre todo.""", [
        ("b10-1-avisos-nivel1", "La bandeja de avisos del cliente: uno al día, el que más le toca."),
    ], None),
    ("11 · Reportes y check-in", """El «no puedo esta semana» completo (aplazar con nota y sin
     más recordatorios), el % de grasa dentro del mensual detrás del peso solo el mes que toca,
     la frase del día programable, el reporte rápido del nivel básico y el PDF de la rutina.""", [
        ("b11-1-inicio-nivel1", "Inicio: la frase del día en cursiva y «¿Cómo fuiste hoy? · Para rellenar al final del día»."),
        ("b11-4-portada-mensual", "La portada de Seguimiento anuncia el reporte que toca y cuándo abre (el mensual, el viernes a las 10:00), y cuál viene después."),
        ("b11-2-reportes-no-puedo", "El formulario vivo (el semanal del Bronze), con el «No puedo esta semana» al pie."),
        ("b11-3-aplazar-abierto", "El aplazado en dos pasos, con «¿Quieres decirme algo?» y sin más recordatorios esa semana."),
    ], None),
    ("12 · Los cuatro paneles", """/admin/paneles: Dirección con el dinero real (entra esta
     semana, cartera pagando, previsión de renovaciones a 4 semanas con importes editables),
     Entrenador filtrado por sus clientes, Operaciones y Soporte con «asignar tarea» desde
     cada lista. En producción, Dirección ya vive con los cobros reales de Stripe.""", [
        ("b12-1-panel-direccion", "Dirección: los cuatro números gordos, la previsión por semanas y «de dónde vienen los que entran»."),
        ("b12-2-panel-entrenador", "Entrenador: el reporte semanal de SUS clientes (lo han mandado, les toca, aplazados, fotos, señales de abandono)."),
        ("b12-3-panel-operaciones", "Operaciones: bloqueados por decisión, cierres de hoy, sin entrenador, sin datos y la lista de Francisco."),
        ("b12-4-panel-soporte", "Soporte: renovaciones por contactar (verde confirmado, ámbar por confirmar), problemas de pago y sin contactar."),
    ], None),
    ("13 · Renovaciones y acceso", """Nada renueva solo: todo el mundo renueva a mano con su
     aviso una semana antes, los planes antiguos se pueden renovar al precio de siempre, y
     renovar antes de tiempo encadena el ciclo sin perder ni una semana. El que se registra y
     no paga siempre tiene el camino de vuelta a los planes.""", [
        ("b13-1-sinplan-inicio", "Sin plan: «Elige tu plan» es lo primero que ve en Inicio."),
        ("b13-2-sinplan-perfil", "Su perfil: tarjeta «Sin plan activo · Ver los planes», y ya no sale el «No quiero renovar» sin sentido."),
        ("b13-4-porvencer-renovacion", "A 5 días de vencer: la pantalla de renovación con sus opciones y el aviso de que la renovación la confirma él."),
        ("b13-6-caducado-renovacion", "Vencido: «Tu ciclo ha terminado» y puede recontratar su mismo plan."),
        ("b13-7-legacy-seguir-igual", "Un plan antiguo (Silver de 149 €): «Seguir igual» a su precio congelado, por pasarela."),
    ], """El repaso cazó y dejó arreglado un texto viejo: la pantalla decía «si no haces nada,
     tu plan se renueva solo», que dejó de ser verdad el 20-08. Ahora esa frase solo sale si
     Stripe le cobra de verdad (clientes antiguos con suscripción viva), y al resto se le dice
     lo contrario: que la renovación la confirma él, y que renovar antes encadena el ciclo."""),
    ("Doc 57 · Los fallos del recorrido de Juan", """Los 8 fallos del recorrido de Juan
     Montalvo, diagnosticados con su causa y arreglados: el clic que se perdía (F1), la fecha
     antigua que tiraba Nutrición (F2), el recuadre automático al cruzar el umbral de frutos
     secos (F3), las favoritas migradas mal etiquetadas (F4, 225 corregidas en producción),
     el «Cuadrar ahora» al aplicar una favorita corta (F5), el aviso que tapaba las pestañas
     (F6), la procedencia de los menús (F7) y el orden del selector (F8).""", [
        ("b57-1-fecha-antigua", "F2: el 24-01-2024 (una favorita de Juan) carga con su aviso de «día muy atrás» en vez de caerse."),
        ("b57-2-selector-procedencia", "F7+F8: el selector abre con un menú con gramos y etiquetas, cada tarjeta dice su procedencia y está el interruptor «Recetario y gente / Solo recetario»."),
        ("b57-3-solo-recetario", "«Solo recetario» activado: los menús de otros usuarios desaparecen, y la elección se recuerda."),
    ], None),
]

F7_DETALLE = """
<section class="bloque" id="f7">
  <h2>La decisión de la biblioteca compartida (F7), explicada</h2>
  <p><strong>El problema.</strong> En «Sugiéreme un menú» conviven las recetas del recetario
  (curadas por el equipo) y los menús que montan los propios clientes (mucho volumen y gramos
  exactos). En el recorrido de Juan, un menú «cuadrado» de la biblioteca traía un donut
  bombón: los números cuadran, pero salía como si lo recomendara Jesús, y el cliente no tenía
  forma de distinguir la procedencia.</p>
  <p><strong>La solución tomada (decisión de Francisco, 21-08).</strong> Separar y etiquetar:
  cada tarjeta dice de dónde viene («Del recetario» / «De otros usuarios») y hay un
  interruptor «Recetario y gente / Solo recetario» que se recuerda entre sesiones. No se
  filtra contenido: se cuenta la verdad y se da la puerta.</p>
  <p><strong>Las otras opciones, por si algún día se quiere endurecer:</strong></p>
  <ul>
    <li><strong>Lista negra de categorías</strong> (bollería, ultraprocesados dulces...):
    mata el caso del donut sin perder volumen, pero siempre se puede colar algo que no esté
    en la lista.</li>
    <li><strong>Solo lo aprobado por el equipo</strong>: máximo control de marca; a cambio se
    pierde el volumen, que es lo que hace que casi siempre haya un menú que clave los macros.
    Se puede llegar por goteo: ir marcando favoritos del equipo con el tiempo.</li>
  </ul>
</section>
"""

def render():
    partes = []
    partes.append("""<title>Repaso de la app · 21-08</title>
<style>
:root { --brand: #FF671F; --fondo: #0d0d0f; --tarjeta: #17171a; --texto: #e8e8ea; --apagado: #9a9aa2; --linea: #26262b; --ok: #34d399; }
:root[data-theme="light"] { --fondo: #f6f6f4; --tarjeta: #ffffff; --texto: #16161a; --apagado: #5b5b64; --linea: #e2e2df; }
* { box-sizing: border-box; }
body { background: var(--fondo); color: var(--texto); font: 16px/1.6 system-ui, sans-serif; margin: 0; padding: 2rem 1rem 5rem; }
main { max-width: 980px; margin: 0 auto; }
h1 { font-size: 1.9rem; line-height: 1.2; text-transform: uppercase; margin: 0 0 .3rem; }
.sub { color: var(--apagado); margin: 0 0 2.2rem; }
.bloque { background: var(--tarjeta); border: 1px solid var(--linea); border-radius: 14px; padding: 1.4rem 1.5rem; margin-bottom: 1.6rem; }
.bloque h2 { margin: 0 0 .6rem; font-size: 1.25rem; color: var(--brand); }
.bloque > p { margin: .4rem 0 1rem; }
figure { margin: 1.1rem 0; }
figure img { width: 100%; max-width: 100%; border-radius: 10px; border: 1px solid var(--linea); display: block; }
figcaption { font-size: .85rem; color: var(--apagado); margin-top: .45rem; }
.nota { border-left: 3px solid var(--brand); padding: .5rem .9rem; background: color-mix(in srgb, var(--brand) 7%, transparent); border-radius: 6px; font-size: .92rem; }
.sello { display: inline-block; font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--ok); border: 1px solid color-mix(in srgb, var(--ok) 45%, transparent); padding: .15rem .6rem; border-radius: 999px; margin-bottom: .8rem; }
ul { padding-left: 1.2rem; }
.cierre { color: var(--apagado); font-size: .9rem; margin-top: 2.4rem; }
</style>
<main>
<h1>La app, bloque a bloque, como queda hoy</h1>
<p class="sub">Repaso del 21 de agosto: los bloques 07-13 del documento del 19 y los fallos del
recorrido de Juan (doc 57), cada cambio probado en la aplicación con cuentas creadas para cada
estado, y con su pantalla real debajo.</p>
""")
    for titulo, intro, capturas, nota in BLOQUES:
        partes.append(f'<section class="bloque">\n<h2>{titulo}</h2>\n<span class="sello">Probado hoy en la app</span>\n<p>{intro}</p>')
        for cap, pie in capturas:
            data = img(cap)
            if data:
                partes.append(f'<figure><img loading="lazy" src="{data}" alt=""><figcaption>{pie}</figcaption></figure>')
            else:
                partes.append(f'<p class="nota">[captura {cap} pendiente] {pie}</p>')
        if nota:
            partes.append(f'<p class="nota">{nota}</p>')
        partes.append('</section>')
    partes.append(F7_DETALLE)
    partes.append("""<p class="cierre">Las cuentas del repaso (todas con password demo123):
prueba.nivel1, prueba.bronze, prueba.porvencer, prueba.caducado, prueba.sinplan,
prueba.legacy y clientedemo, cada una en el estado que enseña su bloque.</p>
</main>""")
    html = "\n".join(partes)
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    open(SALIDA, "w", encoding="utf-8").write(html)
    print(f"escrito {SALIDA} · {os.path.getsize(SALIDA)/1024/1024:.2f} MB")

if __name__ == "__main__":
    render()
