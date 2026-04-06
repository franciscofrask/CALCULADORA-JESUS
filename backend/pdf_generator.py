"""
JG12 Diet PDF Generator
=======================
Genera un PDF profesional con el resumen de la dieta del día.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime


# Colores de la marca JG12
JG12_ORANGE = colors.HexColor("#FF6B00")
JG12_DARK = colors.HexColor("#1a1a2e")
JG12_GRAY = colors.HexColor("#4a4a5a")
JG12_LIGHT_GRAY = colors.HexColor("#f5f5f5")


def generate_diet_pdf(summary: dict, user_name: str = "Cliente", fecha: str = None) -> BytesIO:
    """
    Genera un PDF con el resumen de la dieta del día.
    
    Args:
        summary: Diccionario con la estructura del resumen del día
        user_name: Nombre del usuario
        fecha: Fecha del día (si no se proporciona, usa la fecha actual)
    
    Returns:
        BytesIO con el contenido del PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=JG12_DARK,
        alignment=TA_CENTER,
        spaceAfter=5*mm
    )
    
    style_subtitle = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=JG12_GRAY,
        alignment=TA_CENTER,
        spaceAfter=10*mm
    )
    
    style_section = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=JG12_ORANGE,
        spaceBefore=8*mm,
        spaceAfter=4*mm
    )
    
    style_meal_title = ParagraphStyle(
        'MealTitle',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=JG12_DARK,
        spaceBefore=5*mm,
        spaceAfter=2*mm
    )
    
    style_normal = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=JG12_GRAY
    )
    
    style_footer = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=JG12_GRAY,
        alignment=TA_CENTER
    )
    
    # Contenido del PDF
    elements = []
    
    # Título
    elements.append(Paragraph("JG12 - Tu Dieta del Día", style_title))
    
    # Subtítulo con fecha y nombre
    if not fecha:
        fecha = datetime.now().strftime("%d/%m/%Y")
    elements.append(Paragraph(f"{user_name} • {fecha}", style_subtitle))
    
    # Línea separadora
    elements.append(HRFlowable(width="100%", thickness=1, color=JG12_ORANGE, spaceBefore=2*mm, spaceAfter=5*mm))
    
    # Resumen de macros objetivo
    elements.append(Paragraph("📊 Objetivos del Día", style_section))
    
    objetivo = summary.get("objetivo_total", {})
    totales = summary.get("totales", {})
    diferencia = summary.get("diferencia", {})
    
    # Tabla de resumen
    summary_data = [
        ["", "Objetivo", "Consumido", "Diferencia"],
        [
            "Proteínas (P)",
            f"{objetivo.get('P', 0)}g",
            f"{totales.get('P', 0)}g",
            format_diff(diferencia.get('P', 0))
        ],
        [
            "Hidratos (H)",
            f"{objetivo.get('H', 0)}g",
            f"{totales.get('H', 0)}g",
            format_diff(diferencia.get('H', 0))
        ],
        [
            "Grasas (G)",
            f"{objetivo.get('G', 0)}g",
            f"{totales.get('G', 0)}g",
            format_diff(diferencia.get('G', 0))
        ],
    ]
    
    summary_table = Table(summary_data, colWidths=[50*mm, 35*mm, 35*mm, 35*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), JG12_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), JG12_LIGHT_GRAY),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(summary_table)
    
    # Detalle por comida
    elements.append(Paragraph("🍽️ Detalle de Comidas", style_section))
    
    comidas = summary.get("comidas", [])
    for comida in comidas:
        numero = comida.get("numero", 0)
        alimentos = comida.get("alimentos", [])
        macros = comida.get("macros", {})
        objetivo_comida = comida.get("objetivo", {})
        
        # Título de la comida
        elements.append(Paragraph(f"Comida {numero}", style_meal_title))
        
        if alimentos:
            # Tabla de alimentos
            food_data = [["Alimento", "Cantidad", "P", "H", "G"]]
            
            for alimento in alimentos:
                nombre = alimento.get("nombre", "Sin nombre")
                cantidad = alimento.get("cantidad", 0)
                unidad = alimento.get("unidad", "g")
                macros_alimento = alimento.get("macros", {})
                
                # Formatear cantidad
                if unidad == "ud":
                    cant_str = f"{int(cantidad)} ud"
                else:
                    cant_str = f"{cantidad}g"
                
                food_data.append([
                    nombre,
                    cant_str,
                    f"{macros_alimento.get('P', 0)}g",
                    f"{macros_alimento.get('H', 0)}g",
                    f"{macros_alimento.get('G', 0)}g"
                ])
            
            # Fila de totales
            food_data.append([
                "TOTAL",
                "",
                f"{macros.get('P', 0)}g",
                f"{macros.get('H', 0)}g",
                f"{macros.get('G', 0)}g"
            ])
            
            # Fila de objetivo
            food_data.append([
                "Objetivo",
                "",
                f"{objetivo_comida.get('P', 0)}g",
                f"{objetivo_comida.get('H', 0)}g",
                f"{objetivo_comida.get('G', 0)}g"
            ])
            
            food_table = Table(food_data, colWidths=[60*mm, 30*mm, 20*mm, 20*mm, 20*mm])
            food_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), JG12_ORANGE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('LINEBELOW', (0, -3), (-1, -3), 1, JG12_DARK),
                ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor("#ffe0cc")),
                ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), JG12_LIGHT_GRAY),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Oblique'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]))
            elements.append(food_table)
        else:
            elements.append(Paragraph("Sin alimentos registrados", style_normal))
        
        elements.append(Spacer(1, 3*mm))
    
    # Pie de página
    elements.append(Spacer(1, 10*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=JG12_GRAY, spaceBefore=5*mm, spaceAfter=5*mm))
    elements.append(Paragraph(
        f"Generado por JG12 - Método 12en12 de Jesús Gallego • {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        style_footer
    ))
    
    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def format_diff(value: float) -> str:
    """Formatea la diferencia con signo y color."""
    if value > 0:
        return f"+{value}g"
    elif value < 0:
        return f"{value}g"
    else:
        return "0g ✓"
