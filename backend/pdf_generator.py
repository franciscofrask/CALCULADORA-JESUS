"""
JG12 Diet PDF Generator
=======================
Genera un PDF limpio y con marca con el plan de nutrición del día.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime


# Colores de la marca 12EN12
BRAND = colors.HexColor("#FF6B00")
BRAND_SOFT = colors.HexColor("#FFF1E8")
BRAND_EDGE = colors.HexColor("#FFD3B3")
INK = colors.HexColor("#1A1A2E")
MUTED = colors.HexColor("#6B6B7B")
LINE = colors.HexColor("#E7E7EE")
ZEBRA = colors.HexColor("#FAFAFC")
GOOD = colors.HexColor("#16A34A")
WARN = colors.HexColor("#D97706")

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_larga(fecha: str) -> str:
    """'2026-07-20' -> '20 de julio de 2026'. Si no parsea, devuelve tal cual."""
    try:
        d = datetime.strptime(fecha, "%Y-%m-%d")
        return f"{d.day} de {MESES[d.month]} de {d.year}"
    except Exception:
        return fecha or datetime.now().strftime("%d/%m/%Y")


def _kcal(p, h, g) -> int:
    return round((p or 0) * 4 + (h or 0) * 4 + (g or 0) * 9)


def generate_diet_pdf(summary: dict, user_name: str = "Cliente", fecha: str = None) -> BytesIO:
    """Genera el PDF del plan de nutrición del día. `summary` trae tipo_dia,
    objetivo_total, totales (consumido), diferencia y la lista de comidas."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=16 * mm, leftMargin=16 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
        title=f"Plan de nutricion - {user_name}", author="12EN12 - Jesus Gallego",
    )

    styles = getSampleStyleSheet()
    st_brand = ParagraphStyle('brand', parent=styles['Normal'], fontName='Helvetica-Bold',
                              fontSize=19, textColor=colors.white, leading=21)
    st_brand_sub = ParagraphStyle('brandsub', parent=styles['Normal'], fontName='Helvetica',
                                  fontSize=9.5, textColor=colors.white, leading=12)
    st_head_r = ParagraphStyle('headr', parent=styles['Normal'], fontName='Helvetica-Bold',
                               fontSize=11, textColor=colors.white, alignment=TA_RIGHT, leading=14)
    st_head_r2 = ParagraphStyle('headr2', parent=styles['Normal'], fontName='Helvetica',
                                fontSize=9, textColor=colors.white, alignment=TA_RIGHT, leading=12)
    st_section = ParagraphStyle('section', parent=styles['Normal'], fontName='Helvetica-Bold',
                                fontSize=12, textColor=INK, spaceBefore=6 * mm, spaceAfter=2.5 * mm)
    st_meal = ParagraphStyle('meal', parent=styles['Normal'], fontName='Helvetica-Bold',
                             fontSize=10.5, textColor=INK)
    st_meal_kcal = ParagraphStyle('mealk', parent=styles['Normal'], fontName='Helvetica',
                                  fontSize=9, textColor=MUTED, alignment=TA_RIGHT)
    st_food = ParagraphStyle('food', parent=styles['Normal'], fontName='Helvetica',
                             fontSize=8.8, textColor=INK, leading=11)
    st_note = ParagraphStyle('note', parent=styles['Normal'], fontName='Helvetica',
                             fontSize=9, textColor=MUTED)
    st_footer = ParagraphStyle('footer', parent=styles['Normal'], fontName='Helvetica',
                               fontSize=7.5, textColor=MUTED, alignment=TA_CENTER, leading=10)

    tipo_dia = (summary.get("tipo_dia") or "entrenamiento").lower()
    es_entreno = tipo_dia.startswith("entren")
    badge_txt = "DIA DE ENTRENAMIENTO" if es_entreno else "DIA DE DESCANSO"
    objetivo = summary.get("objetivo_total") or {}
    consumido = summary.get("totales") or {}
    diferencia = summary.get("diferencia") or {}
    hay_objetivo = bool(objetivo)

    elements = []

    # ---- Cabecera de marca (banda naranja) ----
    izq = [Paragraph("12EN12", st_brand),
           Paragraph("Método 12en12 · Jesús Gallego", st_brand_sub)]
    der = [Paragraph("Plan de nutrición", st_head_r),
           Paragraph(_fecha_larga(fecha), st_head_r2)]
    header = Table([[izq, der]], colWidths=[100 * mm, 78 * mm])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 5 * mm))

    # ---- Cliente + badge del tipo de día ----
    badge = Table([[badge_txt]], colWidths=[62 * mm])
    badge.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_SOFT if es_entreno else colors.HexColor("#EEF0F4")),
        ('TEXTCOLOR', (0, 0), (-1, -1), BRAND if es_entreno else MUTED),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROUNDEDCORNERS', [8, 8, 8, 8]),
    ]))
    cliente = Table([[Paragraph(f"<b>{user_name}</b>", ParagraphStyle(
        'cli', parent=styles['Normal'], fontSize=12, textColor=INK)), badge]],
        colWidths=[116 * mm, 62 * mm])
    cliente.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(cliente)
    elements.append(Spacer(1, 4 * mm))

    # ---- Tarjetas de macros del día (kcal, P, H, G) ----
    st_card_lbl = ParagraphStyle('cl', parent=styles['Normal'], fontName='Helvetica-Bold',
                                 fontSize=8, textColor=MUTED, leading=10, spaceAfter=3)
    st_card_val = ParagraphStyle('cv', parent=styles['Normal'], fontName='Helvetica-Bold',
                                 fontSize=16, textColor=INK, leading=19)
    st_card_sub = ParagraphStyle('cs', parent=styles['Normal'], fontName='Helvetica',
                                 fontSize=7.5, textColor=MUTED, leading=10, spaceBefore=1)

    def card(label, consum, obj, unidad="g"):
        val = f"{_fmt(consum)}{unidad}"
        sub = f"de {_fmt(obj)}{unidad}" if hay_objetivo else "consumido"
        return [Paragraph(label, st_card_lbl),
                Paragraph(val, st_card_val),
                Paragraph(sub, st_card_sub)]

    kcal_c = consumido.get("kcal", _kcal(consumido.get("P"), consumido.get("H"), consumido.get("G")))
    kcal_o = objetivo.get("kcal", _kcal(objetivo.get("P"), objetivo.get("H"), objetivo.get("G")))
    cards = Table([[
        card("CALORÍAS", kcal_c, kcal_o, " kcal"),
        card("PROTEÍNA", consumido.get("P", 0), objetivo.get("P", 0)),
        card("HIDRATOS", consumido.get("H", 0), objetivo.get("H", 0)),
        card("GRASA", consumido.get("G", 0), objetivo.get("G", 0)),
    ]], colWidths=[44.5 * mm] * 4)
    cards.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (0, -1), 0.8, BRAND_EDGE),
        ('BOX', (1, 0), (1, -1), 0.8, LINE),
        ('BOX', (2, 0), (2, -1), 0.8, LINE),
        ('BOX', (3, 0), (3, -1), 0.8, LINE),
        ('BACKGROUND', (0, 0), (0, -1), BRAND_SOFT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(cards)

    # Reparto calórico + cuadre (una línea informativa)
    if kcal_c:
        pp = round((consumido.get("P", 0) * 4) / kcal_c * 100)
        ph = round((consumido.get("H", 0) * 4) / kcal_c * 100)
        pg = max(0, 100 - pp - ph)
        reparto = f"Reparto calórico:  proteína {pp}%  ·  hidratos {ph}%  ·  grasa {pg}%"
        elements.append(Spacer(1, 2.5 * mm))
        elements.append(Paragraph(reparto, st_note))

    # ---- Detalle por comida ----
    elements.append(Paragraph("Comidas del día", st_section))
    comidas = summary.get("comidas", [])

    if not comidas:
        elements.append(Paragraph("No hay alimentos registrados este día.", st_note))

    for comida in comidas:
        titulo = comida.get("titulo", "Comida")
        alimentos = comida.get("alimentos", [])
        macros = comida.get("macros", {})
        obj_c = comida.get("objetivo", {})
        mkcal = macros.get("kcal", _kcal(macros.get("P"), macros.get("H"), macros.get("G")))

        # Encabezado de la comida (nombre + kcal), tipo "pill"
        cab = Table([[Paragraph(titulo, st_meal),
                      Paragraph(f"{mkcal} kcal", st_meal_kcal)]],
                    colWidths=[130 * mm, 48 * mm])
        cab.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BRAND_SOFT if comida.get("es_peri") else ZEBRA),
            ('LINEBELOW', (0, 0), (-1, -1), 1.2, BRAND if comida.get("es_peri") else LINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))

        block = [cab]

        if alimentos:
            data = [["Alimento", "Cant.", "P", "H", "G", "kcal"]]
            for a in alimentos:
                m = a.get("macros", {})
                cant = a.get("cantidad", 0)
                unidad = a.get("unidad", "g")
                cant_str = f"{int(cant)} ud" if unidad == "ud" else f"{_fmt(cant)} g"
                data.append([
                    Paragraph(a.get("nombre", "-"), st_food),
                    cant_str, _fmt(m.get("P", 0)), _fmt(m.get("H", 0)),
                    _fmt(m.get("G", 0)), _fmt(m.get("kcal", 0)),
                ])
            # Fila consumido de la comida
            data.append(["Total comida", "", _fmt(macros.get("P", 0)), _fmt(macros.get("H", 0)),
                         _fmt(macros.get("G", 0)), _fmt(mkcal)])
            n_rows = len(data)
            filas_style = [
                ('BACKGROUND', (0, 0), (-1, 0), INK),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 8.5),
                ('TEXTCOLOR', (0, 1), (-1, -1), INK),
                ('TOPPADDING', (0, 0), (-1, -1), 4.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
                ('LEFTPADDING', (0, 0), (0, -1), 8),
                ('LINEBELOW', (0, 0), (-1, -2), 0.4, LINE),
                # Fila total
                ('BACKGROUND', (0, -1), (-1, -1), BRAND_SOFT),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('LINEABOVE', (0, -1), (-1, -1), 0.8, BRAND),
                ('BOX', (0, 0), (-1, -1), 0.5, LINE),
            ]
            # Zebra en las filas de alimento
            for r in range(1, n_rows - 1):
                if r % 2 == 0:
                    filas_style.append(('BACKGROUND', (0, r), (-1, r), ZEBRA))
            tabla = Table(data, colWidths=[86 * mm, 22 * mm, 17 * mm, 17 * mm, 17 * mm, 19 * mm])
            tabla.setStyle(TableStyle(filas_style))
            block.append(tabla)

            # Línea de objetivo/cuadre de la comida
            if obj_c:
                dP = round(obj_c.get("P", 0) - macros.get("P", 0), 1)
                dH = round(obj_c.get("H", 0) - macros.get("H", 0), 1)
                dG = round(obj_c.get("G", 0) - macros.get("G", 0), 1)
                cuadra = all(abs(x) <= 4 for x in (dP, dH, dG))
                if cuadra:
                    txt = ("<font color='#16A34A'>&#10004; Cuadra con el objetivo</font> "
                           f"(P {_fmt(obj_c.get('P',0))} · H {_fmt(obj_c.get('H',0))} · G {_fmt(obj_c.get('G',0))})")
                else:
                    txt = ("<font color='#D97706'>Objetivo:</font> "
                           f"P {_fmt(obj_c.get('P',0))} · H {_fmt(obj_c.get('H',0))} · G {_fmt(obj_c.get('G',0))}  "
                           f"({_signo(dP)}P · {_signo(dH)}H · {_signo(dG)}G)")
                block.append(Spacer(1, 1.2 * mm))
                block.append(Paragraph(txt, ParagraphStyle('cuadre', parent=st_note, fontSize=8)))
        else:
            block.append(Paragraph("Sin alimentos.", st_note))

        block.append(Spacer(1, 4 * mm))
        elements.append(KeepTogether(block))

    # ---- Balance del día (si hay objetivo) ----
    if hay_objetivo:
        elements.append(Paragraph("Balance del día", st_section))
        head = ["", "Objetivo", "Consumido", "Diferencia"]
        rows = [head]
        for etq, k in [("Proteína", "P"), ("Hidratos", "H"), ("Grasa", "G")]:
            rows.append([etq, f"{_fmt(objetivo.get(k,0))} g", f"{_fmt(consumido.get(k,0))} g",
                         _signo(diferencia.get(k, 0)) + " g"])
        rows.append(["Calorías", f"{_fmt(kcal_o)} kcal", f"{_fmt(kcal_c)} kcal",
                     _signo(round(kcal_o - kcal_c)) + " kcal"])
        bal = Table(rows, colWidths=[52 * mm, 42 * mm, 42 * mm, 42 * mm])
        bal.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), INK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ZEBRA]),
            ('LINEABOVE', (0, -1), (-1, -1), 0.8, BRAND),
            ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ]))
        elements.append(bal)

    # ---- Pie ----
    elements.append(Spacer(1, 8 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=LINE))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"Generado con la app 12EN12 de Jesús Gallego · {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        st_footer))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def _fmt(v) -> str:
    """Formatea un número: sin decimales si es entero, con uno si no."""
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return str(v)
    return str(int(v)) if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def _signo(v) -> str:
    """Diferencia con signo explícito; 0 se muestra como '0'."""
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return str(v)
    if abs(v) < 0.05:
        return "0"
    return f"+{_fmt(v)}" if v > 0 else f"-{_fmt(abs(v))}"
