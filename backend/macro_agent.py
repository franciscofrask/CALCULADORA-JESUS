"""
AGENTE DE RE-AJUSTE DE MACROS (Tarea 1)
=======================================
Un AGENTE (LLM) que INTERPRETA el contexto de un cliente (macros actuales,
evolucion de peso, el reporte en lenguaje natural, la fase, y el historial de
como el coach ajusto a ESA persona) y PROPONE el siguiente ajuste, como haria
Jesus. Es una SUGERENCIA que el coach revisa.

- Conocimiento = SYSTEM_PROMPT: la metodologia de Jesus. Fuente que manda: el doc
  "EL MODELO PREDICTIVO DE MACROS" (16-07-2026), mas la mineria de clientes/ajustes
  reales (ver _minar_patrones.py).
- Aprende de la persona: se le pasa su propio historial de ajustes (few-shot).
- Guardarrailes: macro_adjust.py valida que la propuesta no haga barbaridades
  (proteina intacta salvo cambio de fase, dentro de suelos, escalones sanos).

Modelo: gpt-5.1 (fuerte, requiere max_completion_tokens). Configurable por env.
"""
import os
import json
from typing import Dict, List, Optional

from openai import AsyncOpenAI

MODEL = os.environ.get("MACRO_AGENT_MODEL", "gpt-5.1")

SYSTEM_PROMPT = """\
Eres el asistente de AJUSTE DE MACROS del entrenador. Tu trabajo es,
cada mes, PROPONER el siguiente ajuste de macros de un cliente para que el COACH lo
revise y confirme. NO decides tu solo: eres una sugerencia razonada. Piensas y
escribes en espanol de Espana, con tuteo, sin tecnicismos innecesarios.

LOS 8 MACROS (gramos): dia de ENTRENO (proteina/hidratos/grasa), INTRA o perientreno
(proteina/hidratos; la grasa del intra es SIEMPRE 0) y dia de DESCANSO
(proteina/hidratos/grasa).
El HC TOTAL del dia de entreno = HC de entreno + HC de intra (se SUMAN).

REGLAS QUE NO SE VIOLAN NUNCA:
A. PROTEINA ESTABLE. En un ajuste mensual normal NO se toca (en los datos se mantiene
   el ~78% de las veces; un tercio de clientes no la cambia jamas). Solo cambia en
   CAMBIO DE FASE, recomposicion grande o quimica (+10 g maximo). Se RECALCULA al
   final del volumen / inicio de la definicion, sobre la nueva masa magra (es cuando
   se ha consolidado la ganancia muscular). Los ajustes normales nunca la tocan.
B. El HC de ENTRENO ES EL QUE MANDA: marca el ritmo y arrastra a los demas. El PRIMER
   ajuste va siempre por ahi. Cuando se habla de "los macros" a secas, es ese numero.
C. El INTRA ACOMPANA al HC de entreno, no va suelto. Tabla de referencia:
     HC entreno 130-170 -> intra 50 | 170-210 -> 60 | 210-260 -> 75 | +260 -> 90
     zona baja / suelo -> intra 15-30
   Si mueves el HC de entreno a otro tramo, mueve el intra al valor del tramo.
D. HIDRATOS Y GRASAS son lo unico que se ajusta (HC+grasa de entreno, o HC+grasa de
   descanso), SOBRE LOS MACROS ACTUALES: no recalcules desde cero.
E. DESCANSO SIEMPRE POR DEBAJO DE ENTRENO: el HC de descanso nunca supera al de
   entreno. Y la grasa de entreno nunca es mayor que la de descanso.
F. SUELOS: la grasa NUNCA baja de 40 g (suelo absoluto). Suelo de definicion completo:
   50 de HC entreno + 15 de intra (65 sumados) + 40-50 de HC descanso, con la grasa en
   su suelo. En el punto mas bajo no se aguanta mas de UN MES: avisa siempre.
G. ESCALONES reales (nada de 20 g fijos ni progresiones lineales): 10, 15, 20, 25, 30,
   40, 50 o 60 g; el de 20 es el mas comun. Cuanto mas arriba, pasos mas pequenos: a
   partir de ~280-300 de HC entreno, minimos. Los valores son multiplos de 5, pero un
   MOVIMIENTO de 5 g no es un escalon: el paso mas pequeno es de 10 (y las grasas se
   mueven siempre de 10 en 10). Vale tambien para el intra, que baja por su secuencia
   90-75-60-50-40-30-15. Si no merece la pena mover 10, no muevas nada.
H. El TECHO y el SUELO son de cada persona, no generales: sacalos de SU historial (la
   suma mas alta a la que ha llegado y el punto mas bajo que ha aguantado). No apliques
   topes inventados.

COMO AJUSTAR:
1. LA FASE MANDA: 'definicion' o 'volumen', y cuantos meses lleva en ella. Una fase va
   del suelo al techo. El CAMBIO DE FASE es otro evento: ajuste mayor y se revisa el
   % graso (que NO se recalcula cada mes).
2. EL PERFIL SE VE EN LOS AJUSTES, no en el cuestionario: mira como ha respondido esta
   persona a los ajustes anteriores (cuanto peso movio cada cambio de HC) y calibra con
   eso.
   Si el historial trae el CRITERIO del coach y la EVALUACION de como salio cada fase,
   son lo mas valioso que tienes: repite lo que funciono y no repitas un ajuste que ya
   se marco como malo. Ojo a de quien fue la culpa: si la fase salio mal porque el
   CLIENTE no cumplio, el ajuste no estaba mal y no hay que cambiar la estrategia.
   TUS PROPIAS PROPUESTAS: el historial te dice cuales las hiciste tu y que hizo el coach
   con ellas. Si te la guardo TAL CUAL, vas bien con esta persona. Si te la CORRIGIO, ahi
   tienes en gramos exactos en que te pasaste o te quedaste corto CON ELLA: aplicalo antes
   de volver a proponer ese mismo movimiento, y si el coach te corrigio dos veces en la
   misma direccion, es un patron suyo y ya no es casualidad. Una correccion suya vale mas
   que cualquier mediana de casos parecidos.
3. PAUTADO-VS-REAL (clave), con tres escalones segun el cumplimiento:
   - NO ha cumplido: el fallo no es del ajuste, es de la persona. NO toques nada
     ("ponte los del mes pasado") y dilo en el feedback.
   - Ha cumplido A MEDIAS (lo tipico: 70%): NUNCA una variacion grande, pero tampoco te
     quedes congelado. Cabe un escalon pequeno si el peso lo pide; si no lo pide, mantener.
   - Ha cumplido de verdad: ajuste normal, del tamaño que toque.
   El cumplimiento es SUBJETIVO ("tu 70% no es mi 70%"): calibra con el historial de ESTA
   persona que significa cumplir para ella, no te quedes con el numero del reporte.
4. RITMO EN % DEL PESO CORPORAL, nunca en kilos sueltos: 1 kg no significa lo mismo en
   una persona de 60 que en una de 100. El peso no baja lineal, baja a saltos; la mejora
   visual suele ir por delante de la bascula.
5. DEFINICION (cuando cumple): se baja LA GRASA PRIMERO (entreno 90->80->70->60->50;
   descanso ->60->50), y despues se recorta hidrato. El intra baja en la secuencia
   90->75->60->50->40->30->15. Referencia: el % graso baja 4-5% al mes; los
   termogenicos entran el segundo mes. Si baja bien, toca poco o nada ("si funciona, no
   lo rompas"); si esta estancado cumpliendo, un escalon.
6. VOLUMEN (cuando cumple): sube poco a poco, nunca agresivo. La grasa acompana al
   hidrato (entreno 70 tipico / 80 raro; descanso ~80 cuando el entreno va alto). Con
   quimica: +10 g de proteina SOLO en descanso (y +10 en entreno si el descanso supera
   a entreno+intra). Al final de la fase se llega a los "macros umbral", donde ya casi
   no se tocan y subir mas hidrato no sube peso: avisalo.
7. ARRANCAR CORTO a proposito: es mas facil subir que recortar.
8. ESTRATEGIAS puntuales (un mes y salir): ZIGZAG (grasa entreno a ~40, grasa descanso a
   ~70, hidratos altos en entreno y muy bajos en descanso) y el "70-40" para
   estancamiento (subir hidratos de entreno, bajarlos en descanso, compensar con
   grasas). Proponlas cuando encajen, avisando de que son temporales.
9. MUJERES: rangos mas bajos y estrechos, se estancan distinto; a cierta edad puede ser
   hormonal (avisa de valorar analitica, no lo "arregles" con macros).
10. PERFIL Y CASOS PARECIDOS. El perfil sale de SU camino (motor = cuanto hidrato tolera,
    por su techo; respondedor = si coge musculo y pierde grasa, por el indice
    hidrato-grasa), no del cuestionario. Usalo asi: su TECHO y su SUELO historicos son los
    limites de esa persona, y sus UMBRALES dicen donde dejo de ser rentable seguir
    moviendo el hidrato (si esta en el umbral, el ajuste rinde poco: dilo). Un buen
    respondedor aguanta mas hidrato con menos grasa; uno malo necesita menos recorte para
    mover el peso. Si te paso las reglas de su perfil (medianas de casos reales), son la
    referencia de que tamano de ajuste funciona en gente como el.
    Ademas, si te paso casos parecidos de otros clientes, usalos igual, y da mas peso a
    los marcados [MISMO PERFIL] (el "cliente gemelo"). Miralos asi: que se movio, cuanto peso hizo despues y si el coach marco la
    fase como buena o mala. Repite lo que funciono en varios casos parecidos y evita lo
    que salio mal por culpa del ajuste. Manda siempre el historial DEL PROPIO cliente:
    los casos ajenos son apoyo, no sustituyen su respuesta individual. Si te apoyas en
    ellos, dilo en el razonamiento ("en casos parecidos, un recorte de 20 movio el peso
    un -1%").
11. Si un dato no esta (no hay reporte, no hay % graso, falta historial), DILO en los
    avisos y baja la confianza. No te lo inventes ni rellenes el hueco.

COMO SE ESCRIBE LO QUE DEVUELVES (punto 4.2 de la revision del 09-08):

12. EN CASTELLANO BIEN ESCRITO, CON TILDES. Este prompt va sin ellas por comodidad al
    teclearlo, y eso se te estaba pegando: salian "definicion", "aun", "venia", "asi",
    "habia", "dia", "logica", "seria" y hasta un acento invertido ("tambien"). Lo que
    escribes lo lee una persona en su pantalla. Espanol de Espana, tuteo, sin voseo ni
    lexico latinoamericano.
13. NI "COACH" NI ABREVIATURAS DE GIMNASIO. Se dice ENTRENADOR. Y las palabras enteras:
    PROTEINA (no "prote"), FARMACOLOGIA o QUIMICA (no "quimio", que es otra cosa muy
    distinta y en un texto sobre la salud de alguien no se puede escribir), HIDRATOS (no
    "hc" suelto en medio de una frase). "Coach" esta fuera de toda la app.
14. EL RAZONAMIENTO ES PARA EL ENTRENADOR, y va a su campo interno: puedes usar el
    lenguaje del metodo (intra, escalon, techo, suelo) y hablar del cliente en tercera
    persona. No es el mensaje que recibe el cliente: ese lo escribe el entrenador.
15. NO DIGAS QUE "SE MANTIENE" LO QUE CAMBIA. Si el intra no lo tenia y ahora le pones un
    numero, eso es ANADIRLO, y hay que decirlo con esa palabra. Y distingue "no tiene
    intra" de "no consta el intra en esa fila del historial": son cosas distintas y en los
    datos vienen marcadas aparte. Si no consta, no concluyas que no lo tenia.

Devuelve SIEMPRE un JSON valido con esta forma exacta:
{
  "propuesta": {
    "entreno": {"proteina": int, "hidratos": int, "grasa": int},
    "perientreno": {"proteina": int, "hidratos": int},
    "descanso": {"proteina": int, "hidratos": int, "grasa": int}
  },
  "cambios": ["texto corto por cada cambio, p.ej. 'HC entreno -20'"],
  "razonamiento": "2-5 frases para el ENTRENADOR explicando el porque, como lo narraria Jesus",
  "avisos": ["avisos para el entrenador: en suelo, cambio de fase, no cumple, hormonal..."],
  "confianza": "alta|media|baja"
}
Todos los numeros en multiplos de 5. Si no procede cambiar nada, devuelve los mismos
macros y explica por que (p.ej. no cumple, o va perfecto)."""


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _intra_legible(p: Optional[Dict]) -> str:
    """El intra, distinguiendo las tres cosas que antes se escribian igual.

    Se pintaba siempre `Intra P-/H-`, y ese guion valia a la vez para "no tiene intra" y
    para "esa fila del historial no guardo el intra". El agente leia el guion del historial
    como un cero y escribia "venia sin intra" -- y dos frases despues "manteniendo el intra
    en 50", contradiciendose con los macros actuales, que si lo traen. Es el problema 3 del
    punto 4.2, y no era del modelo: era del dato, que decia dos cosas con el mismo simbolo.

    En produccion muchas filas de `macro_history` no guardan `peri`, asi que esto no es un
    caso raro: es el caso normal en clientes que vienen de antes.
    """
    if not isinstance(p, dict) or not p:
        return "Intra: NO CONSTA en esta fila (no es lo mismo que no tenerlo)"
    pr = next((p[i] for i in ("proteina", "protein") if p.get(i) is not None), None)
    hc = next((p[i] for i in ("hidratos", "carbs") if p.get(i) is not None), None)
    if pr is None and hc is None:
        return "Intra: NO CONSTA en esta fila (no es lo mismo que no tenerlo)"
    if (pr in (0, None)) and (hc in (0, None)):
        return "Intra: NO TIENE (a cero)"
    return f"Intra P{pr if pr is not None else '-'}/H{hc if hc is not None else '-'}"


def formatear_macros(m: Dict) -> str:
    e, p, d = m.get("entreno", {}), m.get("perientreno", {}), m.get("descanso", {})
    g = lambda x, *k: next((x[i] for i in k if x.get(i) is not None), "-")
    # El HC total del dia de entreno (entreno + intra) es la cifra que usa Jesus
    # para leer donde esta el cliente: la damos ya calculada.
    he, hi = _num(g(e, 'hidratos', 'carbs')), _num(g(p, 'hidratos', 'carbs'))
    total = f" [HC total entreno {he + hi}]" if he is not None and hi is not None else ""
    return (f"Entreno P{g(e,'proteina','protein')}/H{g(e,'hidratos','carbs')}/G{g(e,'grasa','fat')} | "
            f"{_intra_legible(p)} | "
            f"Descanso P{g(d,'proteina','protein')}/H{g(d,'hidratos','carbs')}/G{g(d,'grasa','fat')}{total}")


def construir_contexto(
    macros_actuales: Dict,
    sexo: str,
    fase: str,
    evolucion_peso: List[Dict],
    reporte: Optional[Dict],
    historial_ajustes: Optional[List[Dict]] = None,
    biotipo: Optional[str] = None,
    meses_en_fase: Optional[int] = None,
    porcentaje_graso: Optional[float] = None,
    casos_gemelos: Optional[str] = None,
    perfil: Optional[str] = None,
    hambre_saturacion: Optional[str] = None,
) -> str:
    """Arma el mensaje de usuario con TODO el contexto que el agente debe interpretar."""
    L = []
    L.append(f"PERFIL: sexo={sexo}, biotipo={biotipo or 'desconocido'}, "
             f"fase actual={fase}, meses en fase={meses_en_fase if meses_en_fase is not None else 'desconocido'}, "
             f"% graso={porcentaje_graso if porcentaje_graso is not None else 'sin dato reciente'}.")
    L.append(f"MACROS ACTUALES: {formatear_macros(macros_actuales)}")

    # P9 del cuestionario: no cambio su macro de arranque, pero SI marca con cuanta mano se
    # ajusta a partir de ahora. Quien aguanta de sobra admite un recorte mayor; quien ya lo
    # esta pasando mal, no. Es margen del cliente, no del metodo, asi que se le dice al agente
    # como contexto y no como una regla que lo obligue.
    RITMO = {
        "aguanto_mas": "Dice que aguanta mucho mas de lo que come ahora: en definicion se le puede "
                       "recortar unos 10 g mas de lo habitual.",
        "mucho": "Dice que pasa MUCHA hambre o ansiedad: ajustes suaves, no le aprietes.",
        "normal": "Dice que pasa lo normal estando a dieta: ritmo habitual.",
        "puedo_mas": "Dice que puede comer mas sin problema: en volumen admite subidas mas grandes.",
        "no_puedo_mas": "Dice que no se ve capaz de comer mas: subidas suaves aunque toque subir.",
    }
    if hambre_saturacion in RITMO:
        L.append(f"MARGEN DEL CLIENTE: {RITMO[hambre_saturacion]}")
    # evolucion de peso + ritmo en % del peso corporal (el doc: nunca en kilos sueltos)
    pts = [(p.get('fecha'), p.get('peso')) for p in (evolucion_peso or [])
           if isinstance(p.get('peso'), (int, float))]
    if pts:
        L.append("EVOLUCION DE PESO (fecha: kg): " + "  ".join(f"{f}:{w}" for f, w in pts[-10:]))
        recientes = pts[-10:]
        tramos = []
        for (f0, w0), (f1, w1) in zip(recientes, recientes[1:]):
            if w0:
                tramos.append(f"{f0}->{f1}: {(w1 - w0) / w0 * 100:+.1f}%")
        if tramos:
            L.append("RITMO POR TRAMO (% del peso corporal): " + "  ".join(tramos))
        if pts[0][1]:
            L.append(f"DESDE EL INICIO: {(pts[-1][1] - pts[0][1]) / pts[0][1] * 100:+.1f}% "
                     f"({pts[0][1]} -> {pts[-1][1]} kg)")
    # reporte en lenguaje natural
    if reporte:
        L.append("REPORTE DE ESTE MES (respuestas del cliente):")
        for k, v in reporte.items():
            if v not in (None, "", {}):
                L.append(f"  - {k}: {v}")
    # historial de ajustes de ESTA persona (para aprender su patron). Los ajustes
    # hechos en la app traen ademas el CRITERIO del coach y la EVALUACION de como
    # salio esa fase: es lo mas valioso que hay aqui, usalo.
    if historial_ajustes:
        L.append("HISTORIAL DE AJUSTES DE ESTA PERSONA (como ajusto el coach antes; aprende su patron):")
        for h in historial_ajustes[-12:]:
            L.append(f"  {h.get('fecha','?')}: {formatear_macros(h.get('macros', h))}"
                     + (f" | peso {h.get('peso')}" if h.get('peso') is not None else "")
                     + (f" | %graso {h.get('porcentaje_graso')}" if h.get('porcentaje_graso') is not None else "")
                     + (f" | cumplio: {h.get('cumplimiento')}" if h.get('cumplimiento') else ""))
            # QUE PALANCA movio en ese ajuste (punto 31 del 07-08). Es la decision, no el
            # resultado: "le bajo los hidratos del dia de descanso" dice mas del patron del
            # coach que los ocho numeros de antes y los ocho de despues, que hasta ahora
            # eran lo unico que llegaba aqui y habia que deducir comparandolos.
            if h.get("palancas"):
                L.append(f"      movio: {', '.join(h['palancas'])}")
            if h.get("criterio"):
                L.append(f"      criterio del coach: {h['criterio']}")
            # Que hizo el coach con TU propuesta anterior de ese mes: la mejor correccion
            # que existe, porque es sobre esta persona y sobre un numero concreto.
            # De donde salio ese ajuste. Los que calculo un cuestionario NO son criterio del
            # coach: son el punto de partida de la calculadora. Aprender de ellos como si
            # fueran decisiones suyas ensucia el patron.
            NO_ES_DEL_COACH = {
                "quiz_alta": "no lo decidio el coach: son los macros de arranque que calculo el cuestionario inicial",
                "quiz_ajuste": "no lo decidio el coach: lo recalculo el cuestionario de ajuste del cliente",
                "cliente_calculadora": "no lo decidio el coach: lo cambio el propio cliente desde su calculadora",
            }
            if h.get("origen") in NO_ES_DEL_COACH:
                L.append(f"      OJO: {NO_ES_DEL_COACH[h['origen']]}")
            elif h.get("origen") == "ia":
                L.append("      esa propuesta la hiciste TU y el coach la guardo TAL CUAL")
            elif h.get("origen") == "ia_corregida":
                corr = h.get("correccion_coach") or {}
                partes = [f"{bloque} {campo} {valor:+g}"
                          for bloque, campos in corr.items() for campo, valor in campos.items()]
                L.append("      esa propuesta la hiciste TU y el coach la CORRIGIO"
                         + (f": {', '.join(partes)} respecto a lo que propusiste" if partes else ""))
            ev = h.get("evaluacion") or {}
            if ev.get("resultado"):
                culpa = {"ajuste": "el ajuste no fue bueno", "cliente": "el cliente no cumplio",
                         "otro": "otros motivos"}.get(ev.get("causa"), "")
                L.append(f"      como salio esa fase: {ev['resultado']}"
                         + (f" ({culpa})" if culpa else "")
                         + (f" - {ev['nota']}" if ev.get("nota") else ""))
    # perfil derivado de su camino + las reglas de su perfil (indices JG12)
    if perfil:
        L.append("")
        L.append(perfil)
    # memoria de la cartera: que se hizo en situaciones parecidas y como salio
    if casos_gemelos:
        L.append("")
        L.append(casos_gemelos)
    L.append("\nPropon el ajuste de macros para el proximo mes (para empezar manana). "
             "Responde solo con el JSON.")
    return "\n".join(L)


async def sugerir_ajuste(contexto: str, api_key: Optional[str] = None, model: str = MODEL) -> Dict:
    """Llama al LLM (gpt-5.1) y devuelve la sugerencia estructurada + validacion."""
    client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": contexto}],
        response_format={"type": "json_object"},
        max_completion_tokens=3000,
    )
    raw = resp.choices[0].message.content
    try:
        out = json.loads(raw)
    except Exception:
        return {"error": "respuesta no-JSON", "raw": raw}
    out["_modelo"] = model
    return out


# Intra que corresponde a cada tramo de HC de entreno (doc: el intra acompana al
# HC de entreno, no va suelto).
def intra_esperado(hc_entreno: Optional[float]) -> Optional[int]:
    if hc_entreno is None:
        return None
    if hc_entreno < 130:
        return None      # zona baja / suelo: 15-30, se valida como rango aparte
    if hc_entreno < 170:
        return 50
    if hc_entreno < 210:
        return 60
    if hc_entreno < 260:
        return 75
    return 90


ESCALONES = (0, 10, 15, 20, 25, 30, 40, 50, 60)
SUELO_GRASA = 40

# CUANTO SE MUEVE EN TOTAL, no macro a macro. Punto 4.2 de la revision del 09-08: la IA
# propuso "HC entreno -20, grasa entreno -10, HC descanso -20" y cada uno de los tres es un
# escalon legal del metodo, asi que el guardarrail no decia nada. Pero suman 50 g en un solo
# ajuste, y "40 g o mas es un cambio de fase, no un ajuste prudente".
#
# Esto NO bloquea ni cambia la propuesta: la saca a la vista, que es lo que se puede hacer
# sin decidir por Jesus. **El numero esta pendiente de que el lo confirme**: sale de una
# frase de su revision, no de su documento de metodo.
MOVIMIENTO_DE_CAMBIO_DE_FASE = 40


def validar(propuesta: Dict, macros_actuales: Dict, avisos_llm: List[str]) -> List[str]:
    """Guardarrail deterministico: marca si la propuesta viola la metodologia
    (no hard-block; son avisos para el coach). Reglas del doc 'El modelo predictivo
    de macros'."""
    warns = []
    g = lambda m, blk, *k: next((m.get(blk, {}).get(i) for i in k if m.get(blk, {}).get(i) is not None), None)
    # proteina intacta salvo cambio de fase mencionado
    cambio_fase = any("fase" in (a or "").lower() for a in (avisos_llm or []))
    for blk in ("entreno", "descanso"):
        pa = g(macros_actuales, blk, "proteina", "protein")
        pp = g(propuesta, blk, "proteina")
        if pa is not None and pp is not None and pp != pa and not cambio_fase:
            warns.append(f"La proteina de {blk} cambio ({pa}->{pp}) sin cambio de fase: revisar (deberia ser estable).")
    # rangos sanos y multiplos de 5
    for blk, campos in (("entreno", ("proteina", "hidratos", "grasa")),
                        ("perientreno", ("proteina", "hidratos")),
                        ("descanso", ("proteina", "hidratos", "grasa"))):
        for c in campos:
            v = g(propuesta, blk, c)
            if v is None:
                warns.append(f"Falta {blk}.{c} en la propuesta."); continue
            if v % 5 != 0:
                warns.append(f"{blk}.{c}={v} no es multiplo de 5.")
            if c == "proteina":
                lo, hi = (15, 80) if blk == "perientreno" else (100, 260)  # peri va aparte (intra/post)
            elif c == "grasa":
                lo, hi = 30, 90
            else:  # hidratos
                lo, hi = 0, 360
            if not (lo <= v <= hi):
                warns.append(f"{blk}.{c}={v} fuera de rango sensato ({lo}-{hi}).")

    he, hd = g(propuesta, "entreno", "hidratos"), g(propuesta, "descanso", "hidratos")
    ge, gd = g(propuesta, "entreno", "grasa"), g(propuesta, "descanso", "grasa")
    hi_intra = g(propuesta, "perientreno", "hidratos")
    he_a = g(macros_actuales, "entreno", "hidratos", "carbs")
    hd_a = g(macros_actuales, "descanso", "hidratos", "carbs")
    ge_a = g(macros_actuales, "entreno", "grasa", "fat")
    gd_a = g(macros_actuales, "descanso", "grasa", "fat")

    def _estructural(mal_propuesta, mal_actual, texto):
        """Avisa de una regla estructural rota. Si los macros ACTUALES ya la
        incumplian, lo dice asi: el coach no la ha roto con este ajuste."""
        if not mal_propuesta:
            return
        warns.append(("Ya venia asi (no lo empeora este ajuste): " if mal_actual else "") + texto)

    # descanso siempre por debajo de entreno
    _estructural(he is not None and hd is not None and hd >= he,
                 he_a is not None and hd_a is not None and hd_a >= he_a,
                 f"el HC de descanso ({hd}) no puede igualar ni superar al de entreno ({he}).")
    _estructural(ge is not None and gd is not None and ge > gd,
                 ge_a is not None and gd_a is not None and ge_a > gd_a,
                 f"la grasa de entreno ({ge}) no puede ser mayor que la de descanso ({gd}).")

    # suelo absoluto de grasa
    for blk, v, va in (("entreno", ge, ge_a), ("descanso", gd, gd_a)):
        _estructural(v is not None and v < SUELO_GRASA,
                     va is not None and va < SUELO_GRASA,
                     f"la grasa de {blk} ({v}) baja del suelo absoluto de {SUELO_GRASA} g.")

    # El intra acompana al HC de entreno. La tabla del doc son MEDIANAS (los clientes
    # reales van por debajo), asi que solo avisamos si se aleja mucho (mas de dos
    # escalones) o si se mueve en direccion contraria al HC de entreno.
    if he is not None and hi_intra is not None:
        esperado = intra_esperado(he)
        if esperado is None:
            if not (15 <= hi_intra <= 30):
                warns.append(f"Con HC de entreno {he} (zona baja) el intra deberia estar entre 15 y 30, no {hi_intra}.")
        elif abs(hi_intra - esperado) > 30:
            warns.append(f"El intra ({hi_intra}) se aleja mucho de la referencia del tramo "
                         f"(HC entreno {he} -> intra ~{esperado}).")
        he_act = g(macros_actuales, "entreno", "hidratos", "carbs")
        hi_act = g(macros_actuales, "perientreno", "hidratos", "carbs")
        if he_act is not None and hi_act is not None:
            if (he - he_act) * (hi_intra - hi_act) < 0:
                warns.append(f"El intra va en direccion contraria al HC de entreno "
                             f"(entreno {he_act}->{he}, intra {hi_act}->{hi_intra}): el intra lo acompana.")

    # escalones reales respecto a los macros actuales (el intra tambien: su secuencia
    # es 90-75-60-50-40-30-15, nunca saltos de 5)
    for blk, campo in (("entreno", "hidratos"), ("entreno", "grasa"),
                       ("perientreno", "hidratos"),
                       ("descanso", "hidratos"), ("descanso", "grasa")):
        act = g(macros_actuales, blk, campo, {"hidratos": "carbs", "grasa": "fat"}[campo])
        nue = g(propuesta, blk, campo)
        if act is None or nue is None:
            continue
        salto = abs(nue - act)
        if salto and salto not in ESCALONES:
            warns.append(f"El salto de {campo} en {blk} ({act}->{nue}, {salto} g) no es un escalon del metodo "
                         f"(10/15/20/25/30/40/50/60).")

    # CUANTO SE MUEVE EN TOTAL, no macro a macro. Tres escalones legales por separado pueden
    # sumar un cambio de fase: -20 de HC entreno, -10 de grasa entreno y -20 de HC descanso
    # son 50 g de una sentada, y los tres pasaban el control de arriba sin decir nada.
    movidos = []
    total_movido = 0
    for blk, campo in (("entreno", "hidratos"), ("entreno", "grasa"),
                       ("perientreno", "hidratos"),
                       ("descanso", "hidratos"), ("descanso", "grasa")):
        act = g(macros_actuales, blk, campo, {"hidratos": "carbs", "grasa": "fat"}[campo])
        nue = g(propuesta, blk, campo)
        if act is None or nue is None or nue == act:
            continue
        total_movido += abs(nue - act)
        movidos.append(f"{campo} de {blk} {nue - act:+d}")
    if total_movido >= MOVIMIENTO_DE_CAMBIO_DE_FASE and not cambio_fase:
        warns.append(
            f"El ajuste mueve {total_movido} g en total ({', '.join(movidos)}). "
            f"Desde {MOVIMIENTO_DE_CAMBIO_DE_FASE} g eso es un cambio de fase, no un ajuste "
            f"prudente: revisa si de verdad toca mover tanto de una vez.")
        sin_datos = any(t in (a or "").lower()
                        for a in (avisos_llm or [])
                        for t in ("no hay dato", "sin dato", "no hay datos", "falta"))
        if sin_datos:
            warns.append("Y la propia propuesta avisa de que le faltan datos: un movimiento "
                         "asi de grande a ciegas no se sostiene.")
    return warns
