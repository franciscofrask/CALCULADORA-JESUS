# -*- coding: utf-8 -*-
"""REPASO PUNTO POR PUNTO DE LOS TRES DOCUMENTOS, con la prueba de cada uno.

No comprueba «esta hecho»: comprueba QUE LA FRASE DE JESUS ESTA EN EL CODIGO. Es la unica
prueba que no se puede discutir. Cada punto lleva:

  - el texto literal del documento,
  - donde tendria que estar,
  - y el fichero y la linea donde esta de verdad (o el hueco, si no esta).

Uso:  ./venv/Scripts/python.exe ../_guia/_repaso_tres_documentos.py
      (desde backend/, o con RAIZ apuntando al repositorio)
"""
import io
import json
import os
import re
import subprocess
import sys

RAIZ = os.environ.get("RAIZ") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (documento, bloque, punto, que dice el documento, [frases que tienen que estar], donde)
PUNTOS = [
    # ════════════════════════════════════════════════════════════════════════
    # DOCUMENTO 1 · «Todo lo validado antes del 1 de septiembre»
    # ════════════════════════════════════════════════════════════════════════
    ("validado", "1 · Inicio y Nutrición", "Abre en Llevas, no en Macros",
     "«Entra y ve 146 · 69 · 49: por dónde va hoy, y lo que le queda.»",
     ["useState('llevas')"], "frontend/src/components/inicio/TuDietaHoy.jsx"),

    ("validado", "1 · Inicio y Nutrición", "Los números, peso 700 y estirados",
     "«Peso 700, estirados a lo alto y estrechados. Ocupan menos ancho.»",
     ["scaleY(1.12) scaleX(0.9)", "'wght' 700"], "frontend/src/index.css · .numero-grande"),

    ("validado", "1 · Inicio y Nutrición", "Los números de Nutrición, como los de Inicio",
     "«44 px y el mismo estirado. Los dos sitios dicen lo mismo igual.»",
     ["numero-grande font-data leading-none text-[44px]"], "TuDietaHoy.jsx y DayHeader.jsx"),

    ("validado", "1 · Inicio y Nutrición", "El tramo de frutos secos, marcado",
     "«El suyo en naranja. De un vistazo sabe que hoy no le cuenta.»",
     ["tramo-suyo-", "aria-current"], "frontend/src/pages/FoodSearchPage.jsx"),

    ("validado", "1 · Inicio y Nutrición", "Extras: el buscador delante",
     "«Si comes algo que no está en tu dieta del día, ponlo aquí, por pequeño que sea.»",
     ["ponlo aquí, por pequeño que sea"], "frontend/src/components/nutrition/ExtrasDelDia.jsx"),

    ("validado", "1 · Inicio y Nutrición", "Extras: «o si no está»",
     "El separador entre el buscador y la caja de texto.",
     ["o si no está"], "frontend/src/components/nutrition/ExtrasDelDia.jsx"),

    ("validado", "1 · Inicio y Nutrición", "Extras: qué pasa con lo que escribe a mano",
     "«Lo que pongas a mano no cuenta en tus macros, simplemente queda el registro. Lo que busques, sí.»",
     ["no cuenta en tus macros", "Lo que busques, sí"],
     "frontend/src/components/nutrition/ExtrasDelDia.jsx"),

    ("validado", "1 · Inicio y Nutrición", "Extras: el día ya cuenta con ellos",
     "«Con dos extras. El día ya cuenta con ellos.»",
     ["en extras"], "frontend/src/components/nutrition/ExtrasDelDia.jsx"),

    ("validado", "1 · Inicio y Nutrición", "La comida por dentro, en su voz",
     "«Te ajusto las cantidades sin pasarme de tus macros.»",
     ["Te ajusto las cantidades sin pasarme de tus macros"], "frontend/src"),

    ("validado", "2 · Los textos", "Suplementos: el nombre y sin mandar al chat",
     "«Todavía no tienes tu plan de suplementación personalizado / Estamos en ello, te avisamos en cuanto esté.»",
     ["plan de suplementación personalizado", "Estamos en ello, te avisamos en cuanto esté"],
     "frontend/src"),

    ("validado", "2 · Los textos", "Rutina sin asignar",
     "«Todavía no tienes tu rutina personalizada / Estamos en ello, te avisamos en cuanto esté.»",
     ["tu rutina personalizada"], "frontend/src"),

    ("validado", "2 · Los textos", "La rutina del mes que no está",
     "«Todavía no está la rutina de este mes»",
     ["la rutina de este mes"], "frontend/src"),

    ("validado", "2 · Los textos", "El aviso de cuando algo falla",
     "«Esto parece cosa nuestra, no tuya. Inténtalo una vez más y, si la cosa sigue igual, escribe por el chat.»",
     ["Esto parece cosa nuestra", "escribe por el chat"], "frontend/src"),

    ("validado", "2 · Los textos", "El texto de la guía de suplementos",
     "«Estos son los suplementos que yo más recomiendo con pautas exactas de uso… te recomiendo empezar por los básicos.»",
     ["te recomiendo empezar por los básicos"], "frontend/src"),

    ("validado", "2 · Los textos", "El texto del código de FullGas",
     "«Lo tendrás activo mientras dure tu suscripción, con un 20 % en toda la web.»",
     ["mientras dure tu suscripción"], "frontend/src"),

    ("validado", "2 · Los textos", "Las tres frases intocables",
     "«Su proteína no te cuenta» · «Te cuentan los tres» · «No te cuenta nada: come lo que quieras»",
     ["Su proteína no te cuenta", "Te cuentan los tres", "No te cuenta nada"],
     "frontend/src + backend"),

    ("validado", "3 · El día", "El cierre: entra la suplementación",
     "«¿Tomaste la suplementación que tenías pautada?»",
     ["¿Tomaste la suplementación que tenías pautada?"], "frontend/src/pages/CheckInsPage.jsx"),

    ("validado", "3 · El día", "El cierre: salen las sensaciones del día y el peso",
     "«Nueve preguntas y las notas. Salen las sensaciones del día y el peso.»",
     ["Sensaciones generales"], "frontend/src/pages/CheckInsPage.jsx"),

    ("validado", "3 · El día", "Extras: «si no lo pusiste, ponlo ahora»",
     "«Si no lo pusiste en el apartado de extras, ponlo ahora»",
     ["Si no lo pusiste en el apartado de extras"], "frontend/src/pages/CheckInsPage.jsx"),

    ("validado", "3 · El día", "Si no le falta nada: el día, todo bien",
     "«El día, todo bien · No te queda nada por registrar», en verde.",
     ["El día, todo bien", "No te queda nada por registrar"], "frontend/src/pages/CheckInsPage.jsx"),

    ("validado", "3 · El día", "Antes de guardar: las ocho enteras",
     "Sin cortar con «y 5 más».",
     ["Te queda por contestar"], "frontend/src/pages/CheckInsPage.jsx"),

    ("validado", "3 · El día", "Ayer no cerraste el día",
     "«Ayer no cerraste el día · Puedes hacerlo hasta las 3 de la tarde»",
     ["Ayer no cerraste el día", "hasta las 3 de la tarde"], "frontend/src"),

    ("validado", "3 · El día", "Tras 2 días perdidos",
     "«Llevas 2 días seguidos sin cerrar, no lo dejes hoy también»",
     ["no lo dejes hoy también"], "frontend/src + backend"),

    ("validado", "3 · El día", "Tras 4 días perdidos",
     "«Retómalo hoy mismo: es de donde salen tus ajustes»",
     ["es de donde salen tus ajustes"], "frontend/src + backend"),

    ("validado", "3 · El día", "Tras una semana",
     "«Dejo de recordártelo. Si te está costando, dímelo y lo vemos»",
     ["Dejo de recordártelo"], "frontend/src + backend"),

    ("validado", "4 · Avisos y peso", "Los siete interruptores y la hora",
     "«Siete interruptores y un selector de hora.»",
     ["Rellenar el cierre del día", "Recordármelo si me lo salto"], "frontend/src"),

    ("validado", "4 · Avisos y peso", "El quincenal y el mensual no se apagan",
     "«El quincenal y el mensual no se pueden desactivar: son los que hacen tu ajuste.»",
     ["no se pueden desactivar"], "frontend/src"),

    ("validado", "4 · Avisos y peso", "Al apagar el cierre del día",
     "«Si lo apagas, no podrás registrar tus datos del día, pero deberás rellenar las preguntas del reporte quincenal y del reporte mensual…»",
     ["no podrás registrar tus datos del día"], "frontend/src"),

    ("validado", "4 · Avisos y peso", "El campo del peso, abierto todo el año",
     "«Registrarlo es opcional, sólo para ti. Te lo pediremos sólo para los reportes.»",
     ["sólo para ti"], "frontend/src"),

    ("validado", "4 · Avisos y peso", "La fila de la mañana",
     "«Hoy toca pesarte · En ayunas y después de ir al baño», y a las 12:00 se apaga.",
     ["toca pesarte"], "backend/core/avisos_cliente.py"),

    ("validado", "4 · Avisos y peso", "El aviso del martes",
     "«Esta semana toca reporte quincenal. Recuerda pesarte y registrar el dato…»",
     ["Esta semana toca reporte quincenal"], "backend"),

    ("validado", "4 · Avisos y peso", "El aviso de la pesada que falta",
     "«Te falta una pesada. Si te pesas esta mañana antes de las 10, aún entra.»",
     ["Te falta una pesada"], "backend"),

    ("validado", "4 · Avisos y peso", "La semana sin reporte",
     "«Esta semana no toca reporte. Solo el cierre del día, como siempre.»",
     ["Esta semana no toca reporte"], "backend"),

    ("validado", "5 · El quincenal", "Son 3 pasos",
     "«Con Son 3 pasos arriba en las tres, y el suyo marcado.»",
     ["Son 3 pasos"], "frontend/src/components/reports"),

    ("validado", "5 · El quincenal", "Paso 1 · Actualizar tus datos",
     "«Sale de tu check-in. Si algo no cuadra o te falta, lo modificas al final.»",
     ["Sale de tu check-in"], "frontend/src/components/reports"),

    ("validado", "5 · El quincenal", "Paso 2 · Tus sensaciones y tus dudas",
     "«¿Algún ejercicio que te dé molestias o alguna máquina que no tengas?»",
     ["alguna máquina que no tengas"], "frontend/src/components/reports"),

    ("validado", "5 · El quincenal", "Paso 3 · Este tercer paso es cosa nuestra",
     "«Recibirás respuesta antes del viernes a las 3, hora de España.»",
     ["Este tercer paso es cosa nuestra"], "frontend/src/components/reports"),

    ("validado", "5 · El quincenal", "Las dos versiones del paso 1",
     "«No tengo todos los datos de tus check-in diarios, así que te lo pregunto aquí.»",
     ["No tengo todos los datos de tus check-in"], "frontend/src/components/reports"),

    ("validado", "5 · El quincenal", "La tarjeta en Hecho",
     "«Respondiste a tiempo y ahora nos toca a nosotros. Te decimos algo antes del viernes a las tres…»",
     ["Respondiste a tiempo"], "frontend/src"),

    ("validado", "5 · El quincenal", "El aviso de la apertura",
     "«Ya puedes rellenar el reporte quincenal. Tienes para hacerlo hasta mañana jueves a las ocho…»",
     ["Ya puedes rellenar el reporte quincenal"], "backend"),

    ("validado", "5 · El quincenal", "El recordatorio del último día",
     "«Solo recordarte que tienes hasta hoy a las ocho…»",
     ["Solo recordarte que tienes hasta hoy"], "backend"),

    ("validado", "5 · El quincenal", "El fuera de plazo",
     "«Se te pasó el plazo del reporte quincenal. Este ajuste se salta.»",
     ["Se te pasó el plazo"], "backend"),

    ("validado", "5 · El quincenal", "La cola de Inicio",
     "«Nunca dos avisos: una lista y un orden.» El reporte arriba, el check-in debajo.",
     ["reporte-${r.tipo}"], "frontend/src/pages/ClientDashboard.jsx"),

    # ════════════════════════════════════════════════════════════════════════
    # DOCUMENTO 2 · «El reporte mensual»
    # ════════════════════════════════════════════════════════════════════════
    ("mensual", "Los cuatro pasos", "La cabecera «Son 4 pasos»",
     "«Con Son 4 pasos en la cabecera de las cuatro, y el suyo marcado.»",
     ["Son 4 pasos", "Actualizar tus datos y confirmar que están bien"],
     "frontend/src/components/reports/PasosDelMensual.jsx"),

    ("mensual", "Paso 1", "El subtítulo del paso 1",
     "«Sale de tus check-in. Si algo no cuadra o te falta, lo arreglas al final.»",
     ["Sale de tus check-in. Si algo no cuadra o te falta, lo arreglas al final"],
     "frontend/src/components/reports/FormularioReporte.jsx"),

    ("mensual", "Paso 1", "El selector de periodo",
     "«El selector de arriba cambia el bloque entero, no solo el peso.» 28 días / desde que empezaste.",
     ["Desde tu último reporte", "Desde que empezaste"],
     "frontend/src/components/reports/MensualPaso1.jsx"),

    ("mensual", "Paso 1", "El peso, con el círculo de su quincenal",
     "«El círculo es el peso de tu quincenal» y «Los círculos son tus reportes anteriores».",
     ["El círculo es el peso de tu quincenal", "Los círculos son tus reportes anteriores"],
     "backend/core/datos_reporte.py"),

    ("mensual", "Paso 1", "Lo que has hecho: las seis filas",
     "Dietas guardadas · Días que comiste de más · Entrenos · Cardio · Movimiento · Suplementación",
     ["Dietas guardadas", "Días que comiste de más", "Movimiento", "Suplementación"],
     "backend/core/actividad_mensual.py"),

    ("mensual", "Paso 1", "Y cómo te has sentido",
     "Descanso · Energía · Hambre / ansiedad, con su media y su línea.",
     ["Hambre / ansiedad", "Solo de estos"], "backend/core/actividad_mensual.py"),

    ("mensual", "Paso 1", "Los huecos, con sus dos respuestas",
     "«Te dejaste 3 entrenos sin registrar» [No entrené / Sí entrené, pero no lo marqué] · «Y 4 días de dieta»",
     ["sin registrar", "No entrené", "Sí entrené, pero no lo marqué",
      "No la cumplí", "Sí, pero no la guardé"], "backend/core/actividad_mensual.py"),

    ("mensual", "Paso 1", "Modificar y Confirmar",
     "Los dos botones del paso 1.",
     ["Modificar", "Confirmar"], "frontend/src/components/reports/MensualPaso1.jsx"),

    ("mensual", "Paso 2", "¿Cuánto te ha costado la dieta?",
     "Una pregunta con cuatro salidas, no dos preguntas.",
     ["¿Cuánto te ha costado la dieta?", "Nada, comiendo así es facilísimo",
      "Sí, baja mis macros porque no llego por mucho que me esfuerce"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 2", "La condicional del cardio",
     "«Si te bajo el número de sesiones, ¿sería viable para que cumplieras?» Solo si falló.",
     ["¿sería viable para que cumplieras?", "Quítamelo, no lo voy a hacer"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 2", "La condicional de la suplementación",
     "«No tomaste la suplementación N días de los 28.» Solo si falló.",
     ["No tomaste la suplementación", "Se me olvidaba", "No quiero seguir tomándola"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 2", "Los ejercicios que dan molestias",
     "«Estos son los que me diste. Quita los que ya no y añade los nuevos»",
     ["Quita los que ya no y añade los nuevos"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 2", "¿Y máquinas que no tienes?",
     "«Actualiza aquí tu listado: si ha entrado alguna nueva, dímelo»",
     ["¿Y máquinas que no tienes?", "si ha entrado alguna nueva, dímelo"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 2", "El grado de compromiso",
     "«Ahora hablo de ti, de si has dado todo o te quedas con la sensación de haber fallado»",
     ["grado de compromiso con el programa", "Mi compromiso es máximo",
      "No he sido capaz de llevarlo a cabo"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 2", "Las expectativas, de 0 a 10",
     "«0 · No, esperaba más» / «10 · Genial, mejor imposible»",
     ["¿el programa está cumpliendo tus expectativas?", "Genial, mejor imposible"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 2", "Dudas o lo que quieras contarme",
     "«Ahora es el momento y el lugar»",
     ["Dudas o lo que quieras contarme", "Ahora es el momento y el lugar"],
     "frontend/src/components/reports/ReporteMensual.jsx"),

    ("mensual", "Paso 3", "Las fotos y su porqué",
     "«Relajado, siempre en el mismo sitio y con la misma luz que las anteriores. Es lo único que me deja comparar.»",
     ["Es lo único que me deja comparar"], "frontend/src/components/reports/MensualPaso3.jsx"),

    ("mensual", "Paso 3", "El metro y el vídeo",
     "«Con el metro pegado y sin apretar. Aquí tienes el vídeo de cómo se toman.»",
     ["Con el metro pegado y sin apretar", "Aquí tienes el vídeo"],
     "frontend/src/components/reports/MensualPaso3.jsx"),

    ("mensual", "Paso 3", "Adónde van a parar",
     "«Las fotos y las medidas van a Mi evolución, con las de los meses anteriores.»",
     ["van a", "Mi evolución"], "frontend/src/components/reports/MensualPaso3.jsx"),

    ("mensual", "Paso 3", "Las medidas, con la del mes pasado al lado",
     "«el mes pasado 127»",
     ["el mes pasado"], "frontend/src/components/reports/MensualPaso3.jsx"),

    ("mensual", "Paso 4", "Ya lo tienes · Tu informe del mes",
     "«Te lo entrego ya. Es un análisis objetivo que sale de toda la información…»",
     ["Tu informe del mes", "análisis objetivo", "Ver mi informe"],
     "frontend/src/components/reports/MensualPaso4.jsx"),

    ("mensual", "Paso 4", "Nuevo programa y feedback",
     "«Analizamos tus respuestas, comparamos fotos y métricas y, a partir de ahí, ajustamos tus macros…»",
     ["Analizamos tus respuestas", "para las próximas 4 semanas"],
     "frontend/src/components/reports/MensualPaso4.jsx"),

    ("mensual", "Paso 4", "Y mientras tanto, mírate",
     "El cierre del paso 4.",
     ["Y mientras tanto, mírate"], "frontend/src/components/reports/MensualPaso4.jsx"),

    ("mensual", "Sin check-in", "Las cinco preguntas con estrellas",
     "«No tengo todos los datos de tus check-in diarios, así que te lo pregunto aquí.»",
     ["No tengo todos los datos de tus check-in"], "frontend/src/components/reports"),

    # ════════════════════════════════════════════════════════════════════════
    # DOCUMENTO 3 · «El informe del mes»
    # ════════════════════════════════════════════════════════════════════════
    ("informe", "Cuándo llega", "Se entrega al enviar",
     "«Se le entrega al enviar, con el hueco del feedback vacío.»",
     ["EL INFORME SE ENTREGA AL ENVIAR"], "backend/routes/reports.py"),

    ("informe", "1 · Dónde estás", "Su objetivo y su semana",
     "«Su objetivo y en qué semana del ciclo va, de cuántas.»",
     ["Bajar grasa", "Ganar músculo", "Semana"], "backend/core/informe_del_mes.py"),

    ("informe", "2 · Tu feedback", "El hueco, en gris y con la hora",
     "«En estos momentos estamos revisando tu reporte mensual. Antes del viernes a las 15:00 te mandamos todo.»",
     ["En estos momentos estamos revisando tu reporte mensual"],
     "backend/core/informe_del_mes.py"),

    ("informe", "2 · Tu feedback", "Y luego tu texto firmado",
     "El bloque de Jesús arriba, con su firma y la fecha.",
     ["iniciales", "firma"], "backend/core/informe_del_mes.py"),

    ("informe", "3 · Tu peso", "Con qué empezó el mes y con cuál lo acaba",
     "«Empezaste el mes en · Lo acabas en · Cuando empezaste pesabas · Desde que empezaste»",
     ["Empezaste el mes en", "Lo acabas en", "Cuando empezaste pesabas"],
     "frontend/src/components/reports/InformeDelMes.jsx"),

    ("informe", "3 · Tu peso", "El porcentaje que ha bajado cada semana",
     "«Porcentaje del peso total que has ido bajando por semana.»",
     ["Porcentaje del peso total que has ido bajando por semana"],
     "frontend/src/components/reports/InformeDelMes.jsx"),

    ("informe", "4 · Tus medidas", "Las diez, contra el mes pasado y la primera toma",
     "«DIEZ TOMAS · MES ANT. · 1ª TOMA»",
     ["Diez tomas", "Mes ant.", "1ª toma"],
     "frontend/src/components/reports/InformeDelMes.jsx"),

    ("informe", "5 · Grasa", "Cada 12 semanas, y cuándo se midió",
     "«Se mide al final de cada ciclo, cada 12 semanas. La última medición: 18 %, el 4 de junio.»",
     ["Se mide al final de cada ciclo", "La última medición"],
     "backend/core/informe_del_mes.py"),

    ("informe", "6 · Tus fotos", "Dos, y las elige él",
     "Pestañas de pose (frente, espaldas, perfil) y dos selectores de fecha.",
     ["informe-pose-", "informe-foto-"], "frontend/src/components/reports/InformeDelMes.jsx"),

    ("informe", "7 · Lo que has hecho", "Dietas, entrenos, cardios y suplementación",
     "«Dietas completas · Cuadradas al 100 % · Comiste de más · Entrenos hechos / Perdidos · Cardios hechos / Perdidos · Suplementación sí / no»",
     ["Dietas completas", "Cuadradas al 100 %", "Entrenos hechos", "Cardios hechos",
      "Suplementación sí"], "backend/core/informe_del_mes.py"),

    ("informe", "8 · Tu día tipo", "La combinación que más repite en cada comida",
     "«La combinación que más repites en cada comida, y cuántos días.»",
     ["La combinación que más repites en cada comida"],
     "frontend/src/components/reports/InformeDelMes.jsx"),

    ("informe", "8 · Tu día tipo", "Cuando cambia casi cada día",
     "«Cambia casi cada día · 17 combinaciones distintas»",
     ["Cambia casi cada día", "combinaciones distintas"], "backend/core/informe_del_mes.py"),

    ("informe", "9 · Preferencias", "Sus tres de cada, con las veces",
     "«Tus fuentes de proteína, hidratos y grasas preferidas, y las veces que las has puesto este mes.»",
     ["las veces que las has puesto"], "frontend/src/components/reports/InformeDelMes.jsx"),

    ("informe", "10 · Extras", "Lo que apuntó y qué día",
     "«Seis días, y cinco cayeron en fin de semana. Lo que apuntaste:»",
     ["cayeron en fin de semana", "Lo que apuntaste"], "backend/core/informe_del_mes.py"),

    ("informe", "Regla", "El informe no le pide nada",
     "«Lo único que puede tocar son los selectores de las fotos y el botón de guardar su desayuno como plantilla.»",
     ["El informe no le pide nada"], "frontend/src/components/reports/InformeDelMes.jsx"),
]


def buscar(frase: str):
    """Devuelve [(fichero, linea, texto)] donde aparece la frase, sin _guia ni tests."""
    try:
        r = subprocess.run(
            ["git", "grep", "-n", "-F", frase, "--", "backend", "frontend"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
    except Exception:                                   # noqa: BLE001
        return []
    salida = []
    for linea in (r.stdout or "").splitlines():
        partes = linea.split(":", 2)
        if len(partes) < 3:
            continue
        fichero, num, texto = partes
        if "/tests/" in fichero or fichero.endswith(".json"):
            continue
        salida.append((fichero, int(num), texto.strip()[:160]))
    return salida


def main() -> None:
    resultado = []
    for doc, bloque, punto, dice, frases, donde in PUNTOS:
        pruebas = []
        faltan = []
        for f in frases:
            hits = buscar(f)
            if hits:
                pruebas.append({"frase": f, "donde": hits[:3], "veces": len(hits)})
            else:
                faltan.append(f)
        resultado.append({
            "doc": doc, "bloque": bloque, "punto": punto, "dice": dice,
            "esperado_en": donde, "pruebas": pruebas, "faltan": faltan,
            "estado": "cerrado" if frases and not faltan else
                      "parcial" if pruebas else
                      "sin_frase" if not frases else "abierto",
        })

    destino = os.path.join(RAIZ, "_guia", "_repaso_tres_documentos.json")
    with io.open(destino, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)

    por_estado = {}
    for r in resultado:
        por_estado[r["estado"]] = por_estado.get(r["estado"], 0) + 1
    print(f"{len(resultado)} puntos · " + " · ".join(f"{k}: {v}" for k, v in sorted(por_estado.items())))
    for r in resultado:
        if r["estado"] != "cerrado":
            print(f"  [{r['estado']}] {r['doc']} · {r['punto']}"
                  + (f"  faltan: {r['faltan']}" if r["faltan"] else ""))
    print(f"\n(detalle en {destino})")


main()
