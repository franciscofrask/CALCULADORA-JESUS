# -*- coding: utf-8 -*-
"""
LOS PUNTOS DE CONTROL, EL COMPARADOR Y EL SELECTOR DE FOTOS Y MEDIDAS (doc de Jesús del
2-09, fase 3; decisiones de Francisco del 4-09).

Jesús: «un punto es un reporte. Ni quincenales ni pesajes sueltos: los reportes son los
únicos que traen fotos y medidas, que es lo que hace que dos puntos se puedan comparar».
La lista va dentro de Evolución, «uno por reporte, del más antiguo al de hoy», cada uno
llamado por «bloque y ciclo», con su objetivo y su peso, y encima las etiquetas: pico de
forma (la pone el entrenador), peso máximo y peso mínimo (salen solas). Al tocar uno: su
foto de ese día, «los macros que llevaba entonces», sus medidas y su grasa. «Cuando falta
algo se dice (no lo mediste en este reporte), nunca un hueco.»

Este módulo COMPONE todo eso en una sola respuesta (`puntos_de`), que sirven igual el
cliente (`GET /reports/puntos`) y el equipo (`GET /admin/clients/{id}/puntos`). Aquí no se
escribe nada: se lee el cuaderno de ciclos (core/ciclos), los reportes, las fotos
(core/fotos, la misma lista y la misma `url` que `GET /reports/photos`), la serie de peso
y de grasa (core/series_cliente), el historial de macros y las tres puertas de las
medidas (`reports.measurements`, `client_profiles.medidas_sueltas` y
`client_profiles.medidas_inicio`).

Las decisiones de Francisco del 4-09 que manda este fichero:

  - NUNCA UN HUECO, NUNCA UN NÚMERO INVENTADO SIN DECIR QUE ES APROXIMADO. El cuaderno de
    ciclos empezó a escribirse el 4-09 y de lo anterior solo se apuntó el ciclo abierto.
    Un reporte de antes no tiene ciclo apuntado (`ciclo_id` a None) y aun así tiene que
    salir con nombre: se sitúa en TRAMOS contados desde el alta (`created_at`, o el
    primer reporte o foto si es anterior), del largo del ciclo de su plan, en bloques de
    cuatro semanas, y se dice `aproximado: true` con «Tramo n» en vez de «Ciclo n».
  - Los objetivos los pone el entrenador y viven en el cuaderno: el objetivo de un punto
    es el de su ciclo. Un tramo aproximado no tiene objetivo (nadie lo puso).
  - El pico de forma es uno por ciclo, lo marca el equipo mientras el ciclo está abierto
    (`ciclos.pico_de_forma`, routes/admin.py) y «no es el peso mínimo»: son dos etiquetas
    distintas y aquí se calculan por separado.
  - El Punto 0: «el que abre un ciclo cuando no hay uno pegado detrás», en dos casos, el
    alta y la vuelta. Solo si no hay un reporte a una semana de ese arranque; si lo hay,
    ese reporte ya es el punto de partida y el 0 sobraría.

Los días son DÍAS DE ESPAÑA (core/ciclos.dia_de_espana): un reporte es un plazo del
negocio, no un instante del reloj del cliente.
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from core.ciclos import SEMANAS_POR_BLOQUE, ciclos_de, dia_de_espana, semanas_del_plan
from core.database import db
from core.fotos import listar_fotos_de
from core.historial_macros import fecha_de_vigencia
from core.objetivos import nombre_de
from core.series_cliente import curva_de_peso, sanea_peso
from core.sin_futuro import hasta_hoy
from core.tiempo import hoy_madrid

logger = logging.getLogger(__name__)

# QUÉ REPORTE ES UN PUNTO. Jesús: el mensual, «ni quincenales ni pesajes sueltos». Y los que
# no llevan `tipo`: medido en dev el 4-09, 3.415 de 3.418 reportes van sin `tipo`, y son
# todos los importados de Calma (`calma_migrated`), donde el único formulario con fotos y
# medidas era el mensual, más los de antes de que el formulario tuviera tipos, cuando el
# único reporte de la app ERA el mensual. Dejarlos fuera vaciaría la lista de casi todos los
# clientes reales: un hueco entero, que es justo lo que Francisco dijo que no.
TIPOS_QUE_SON_PUNTO = (None, "", "mensual")
# Los motivos de ciclo que abren un Punto 0 (doc del 2-09: «el alta y la vuelta»; el
# registro inicial es el alta de quien ya estaba cuando nació el cuaderno).
MOTIVOS_CON_PUNTO_0 = ("alta", "vuelta", "registro_inicial")
# «Si en un ciclo no subió fotos, ese hito no existe. El atajo coge la más cercana y lo
# dice»: hasta una semana se da por la foto (o la toma) de ese hito; más lejos, con nota.
DIAS_DE_MARGEN_HITO = 7
# Peso y grasa de un punto: la medida de la serie a tres días como mucho. Más lejos no es
# el dato de ese reporte y se dice «no lo mediste en este reporte».
DIAS_DE_MARGEN_MEDIDA = 3
# El largo de un tramo aproximado cuando el plan no dice cuánto dura su ciclo.
SEMANAS_DE_TRAMO_POR_DEFECTO = 12
# El orden en que se enseñan las poses, y la que manda en los atajos («siempre el mismo
# ángulo. Comparar un frente con un perfil no dice nada»).
POSES_EN_ORDEN = ("frente", "perfil", "espalda")
POSE_QUE_MANDA = "frente"
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")

_PROYECCION_REPORTE = {
    "_id": 0, "id": 1, "tipo": 1, "weight": 1, "measurements": 1, "photos": 1,
    "created_at": 1, "fecha": 1, "ciclo_id": 1, "ciclo_numero": 1, "ciclo_inicio": 1,
    "semana_del_ciclo": 1, "bloque": 1,
}
_PROYECCION_MACROS = {
    "_id": 0, "id": 1, "effective_date": 1, "created_at": 1, "training": 1, "new_training": 1,
    "rest": 1, "new_rest": 1, "peri": 1, "macros_periworkout": 1, "peso": 1, "client_weight": 1,
}


# ==================== fechas ====================

def _d(dia: str) -> date:
    return date.fromisoformat(dia)


def _sumar_dias(dia: str, n: int) -> str:
    return (_d(dia) + timedelta(days=n)).isoformat()


def _dias_entre(desde: str, hasta: str) -> int:
    return (_d(hasta) - _d(desde)).days


def _distancia(a: str, b: str) -> int:
    return abs(_dias_entre(a, b))


def _en_palabras(dia: str, hoy: str) -> str:
    """«12 de junio», y con el año si no es el de hoy («12 de junio de 2025»)."""
    d = _d(dia)
    texto = f"{d.day} de {MESES[d.month - 1]}"
    if d.year != _d(hoy).year:
        texto += f" de {d.year}"
    return texto


def _dia_del_reporte(reporte: Dict[str, Any]) -> Optional[str]:
    """El día de España en que se mandó (`created_at`), como lo cuenta el informe
    (routes/reports._dia_del_reporte); si no se entiende, `fecha` tal cual."""
    for crudo in (reporte.get("created_at"), reporte.get("fecha")):
        dia = dia_de_espana(crudo)
        if dia:
            return dia
    return None


def _mas_cercano(candidatos: List[Dict[str, Any]], fecha: str, margen: Optional[int],
                 clave: str = "fecha") -> Optional[Dict[str, Any]]:
    """El elemento con `clave` más cerca de `fecha` (a `margen` días como mucho, o sin
    tope con None). En empate gana el más antiguo: la lista llega ordenada y solo se
    sustituye con una distancia estrictamente menor."""
    mejor, mejor_distancia = None, None
    for c in candidatos:
        dia = c.get(clave)
        if not dia:
            continue
        distancia = _distancia(dia, fecha)
        if margen is not None and distancia > margen:
            continue
        if mejor is None or distancia < mejor_distancia:
            mejor, mejor_distancia = c, distancia
    return mejor


# ==================== los grupos: ciclos del cuaderno y tramos aproximados ====================

def _etiqueta(prefijo: str, numero: Any, inicio: str, fin: Optional[str], abierto: bool, hoy: str) -> str:
    """«Ciclo 3 · junio a septiembre», «Ciclo 3 · desde junio» si está abierto, «Tramo 2 ·
    marzo» si empieza y acaba en el mismo mes; con el año cuando no es el de hoy."""
    d_inicio = _d(inicio)
    mes_inicio = MESES[d_inicio.month - 1]
    if abierto or not fin:
        texto = f"desde {mes_inicio}"
    else:
        d_fin = _d(fin)
        if (d_fin.year, d_fin.month) == (d_inicio.year, d_inicio.month):
            texto = mes_inicio
        else:
            texto = f"{mes_inicio} a {MESES[d_fin.month - 1]}"
    if d_inicio.year != _d(hoy).year:
        texto += f" de {d_inicio.year}"
    return f"{prefijo} {numero} · {texto}"


class _Grupos:
    """Dónde cae cada cosa: en un ciclo del cuaderno (exacto) o, si el cuaderno no lo
    cubre, en un tramo contado desde el alta (aproximado, y dicho).

    Un tramo dura lo que el ciclo del plan (`semanas_del_plan`, 12 si el plan no lo dice) y
    se recorta el día antes del primer ciclo del cuaderno que arranque dentro de él: desde
    que hay cuaderno, manda el cuaderno. Solo se crean los tramos que algo necesita."""

    def __init__(self, profile: Dict[str, Any], cuaderno: List[Dict[str, Any]],
                 ancla: Optional[str], hoy: str):
        self.hoy = hoy
        self.ancla = ancla
        self.semanas_tramo = semanas_del_plan(profile) or SEMANAS_DE_TRAMO_POR_DEFECTO
        self.cuaderno = [self._del_cuaderno(c) for c in cuaderno if c.get("inicio")]
        self.cuaderno.sort(key=lambda g: g["inicio"])
        self.por_id: Dict[str, Dict[str, Any]] = {g["id"]: g for g in self.cuaderno}
        self.tramos: Dict[int, Dict[str, Any]] = {}

    def _del_cuaderno(self, c: Dict[str, Any]) -> Dict[str, Any]:
        abierto = not c.get("fin")
        semanas = c.get("semanas") or self.semanas_tramo
        fin_previsto = c.get("fin_previsto")
        # El fin con el que se marca «final»: el cerrado de verdad o, si sigue abierto pero
        # su fin previsto ya pasó (nadie lo cerró), ese. Un fin que aún no ha llegado no
        # tiene «final» que marcar.
        fin_efectivo = c.get("fin") or (fin_previsto if fin_previsto and fin_previsto <= self.hoy else None)
        return {
            "id": c["id"], "numero": c.get("numero"), "inicio": c["inicio"], "fin": c.get("fin"),
            "fin_previsto": fin_previsto, "abierto": abierto, "objetivo": c.get("objetivo"),
            "objetivo_nombre": nombre_de(c.get("objetivo")),
            "etiqueta": _etiqueta("Ciclo", c.get("numero"), c["inicio"], c.get("fin"), abierto, self.hoy),
            "aproximado": False, "motivo": c.get("motivo"), "pico_de_forma": c.get("pico_de_forma"),
            "semanas": semanas, "bloques": max(1, math.ceil(semanas / SEMANAS_POR_BLOQUE)),
            "fin_efectivo": fin_efectivo,
        }

    def de(self, fecha: str, ciclo_id: Optional[str] = None) -> Dict[str, Any]:
        """Primero por el id apuntado; si no, el ciclo del cuaderno que cubre ese día (el
        abierto cubre todo lo que venga después de su inicio, como hace `ciclo_de`); si
        no, un tramo aproximado."""
        if ciclo_id and ciclo_id in self.por_id:
            return self.por_id[ciclo_id]
        for g in reversed(self.cuaderno):
            if g["inicio"] <= fecha and (not g["fin"] or fecha <= g["fin"]):
                return g
        return self._tramo_de(fecha)

    def _tramo_de(self, fecha: str) -> Dict[str, Any]:
        ancla = self.ancla or fecha
        largo = self.semanas_tramo * 7
        n = max(0, _dias_entre(ancla, fecha)) // largo + 1
        if n in self.tramos:
            return self.tramos[n]
        inicio = _sumar_dias(ancla, (n - 1) * largo)
        fin = _sumar_dias(inicio, largo - 1)
        for g in self.cuaderno:
            if inicio < g["inicio"] <= fin:
                recortado = _sumar_dias(g["inicio"], -1)
                # Si el recorte dejara fuera el día que se está situando (un día en el
                # hueco entre un ciclo ya cerrado y el siguiente: el cliente paró y
                # volvió), se deja el tramo entero; es aproximado y lo dice.
                if recortado >= fecha:
                    fin = recortado
                break
        abierto = fin >= self.hoy
        tramo = {
            "id": f"tramo:{n}", "numero": n, "inicio": inicio, "fin": fin, "fin_previsto": None,
            "abierto": abierto, "objetivo": None, "objetivo_nombre": None,
            "etiqueta": _etiqueta("Tramo", n, inicio, fin, abierto, self.hoy),
            "aproximado": True, "motivo": None, "pico_de_forma": None,
            "semanas": self.semanas_tramo,
            "bloques": max(1, math.ceil(self.semanas_tramo / SEMANAS_POR_BLOQUE)),
            "fin_efectivo": fin if fin <= self.hoy else None,
        }
        self.tramos[n] = tramo
        self.por_id[tramo["id"]] = tramo
        return tramo

    def abierto(self) -> Optional[Dict[str, Any]]:
        """El ciclo abierto del cuaderno (el más reciente si hubiera dos)."""
        return next((g for g in reversed(self.cuaderno) if g["abierto"]), None)

    def anterior_al_abierto(self) -> Optional[Dict[str, Any]]:
        """El ciclo CERRADO del cuaderno que precede al abierto (o el último cerrado si no
        hay ninguno abierto). None si el cuaderno no tiene otro: no se inventa."""
        abierto = self.abierto()
        cerrados = [g for g in self.cuaderno if g["fin"] and (not abierto or g["inicio"] < abierto["inicio"])]
        return cerrados[-1] if cerrados else None

    def todos(self) -> List[Dict[str, Any]]:
        return sorted(self.cuaderno + list(self.tramos.values()), key=lambda g: g["inicio"])

    @staticmethod
    def breve(g: Dict[str, Any]) -> Dict[str, Any]:
        """Lo que viaja dentro de cada foto y toma."""
        return {"id": g["id"], "numero": g["numero"], "etiqueta": g["etiqueta"], "aproximado": g["aproximado"]}

    @staticmethod
    def para_la_lista(g: Dict[str, Any]) -> Dict[str, Any]:
        claves = ("id", "numero", "inicio", "fin", "fin_previsto", "abierto", "objetivo",
                  "objetivo_nombre", "etiqueta", "aproximado", "motivo", "pico_de_forma", "semanas")
        return {k: g.get(k) for k in claves}


def _semana_y_bloque(grupo: Dict[str, Any], fecha: str, semana_apuntada=None, bloque_apuntado=None):
    """La semana y el bloque dentro del grupo: los congelados en el documento si los
    trae (mismo cálculo que `ciclo_de`), y si no, contados desde el inicio del grupo."""
    if semana_apuntada and bloque_apuntado and not grupo["aproximado"]:
        return int(semana_apuntada), int(bloque_apuntado)
    semana = max(0, _dias_entre(grupo["inicio"], fecha)) // 7 + 1
    return semana, (semana - 1) // SEMANAS_POR_BLOQUE + 1


# ==================== piezas de un punto ====================

def _bloque_de_macros(m: Optional[Dict[str, Any]], con_grasa: bool = True) -> Optional[Dict[str, Any]]:
    """Un bloque de macros con los nombres de «Mis macros» (la misma salida que
    `routes/users._bloque_de_macros`, copiada aquí para que core no importe de routes):
    en la base conviven `protein/carbs/fat` y `proteinas/hidratos/grasas`, y se sale por
    uno solo."""
    if not isinstance(m, dict):
        return None

    def _n(*nombres):
        for k in nombres:
            v = m.get(k)
            if v is not None:
                try:
                    return round(float(v))
                except (TypeError, ValueError):
                    return None
        return None

    fuera = {"proteina": _n("protein", "proteinas"), "hidratos": _n("carbs", "hidratos")}
    if con_grasa:
        fuera["grasa"] = _n("fat", "grasas")
    return fuera if any(v is not None for v in fuera.values()) else None


def _macros_vigentes(filas: List[Dict[str, Any]], fecha: str) -> Optional[Dict[str, Any]]:
    """«Los macros que llevaba entonces»: la última fila del historial cuya vigencia no
    es posterior al día del punto. Jesús: «esto no necesita datos nuevos: la app ya guarda
    los ajustes con su fecha»."""
    vigente = None
    for h in filas:                       # ordenadas de la más antigua a la más nueva
        if h["fecha"] <= fecha:
            vigente = h
        else:
            break
    if not vigente:
        return None
    peri = vigente.get("peri") or vigente.get("macros_periworkout")
    return {
        "fecha": vigente["fecha"],
        "entreno": _bloque_de_macros(vigente.get("training") or vigente.get("new_training")),
        "descanso": _bloque_de_macros(vigente.get("rest") or vigente.get("new_rest")),
        "peri": _bloque_de_macros(peri, con_grasa=False),
    }


def _medidas_limpias(crudas: Any) -> Optional[Dict[str, float]]:
    """Solo las medidas con número. None si no queda ninguna: «no lo mediste»."""
    if not isinstance(crudas, dict):
        return None
    limpias = {}
    for k, v in crudas.items():
        if k == "fecha":
            continue
        try:
            limpias[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return limpias or None


def _valor_cercano(serie: List[Dict[str, Any]], fecha: str, clave: str) -> Optional[float]:
    punto = _mas_cercano(serie, fecha, DIAS_DE_MARGEN_MEDIDA)
    return punto.get(clave) if punto else None


def _foto_breve(f: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que viaja de una foto dentro de un punto. `url` es la misma firmada que da
    `GET /reports/photos` (None si no la hay: sin R2, o sin objeto en el bucket), y `ref`
    y `fuente` para que el front pueda pedir el binario como siempre si no hay `url`."""
    return {"id": f.get("id"), "pose": f.get("pose"), "taken_at": f.get("taken_at"),
            "fecha": f.get("fecha"), "url": f.get("url"), "ref": f.get("ref"),
            "fuente": f.get("fuente")}


def _orden_de_pose(pose: Optional[str]) -> int:
    return POSES_EN_ORDEN.index(pose) if pose in POSES_EN_ORDEN else len(POSES_EN_ORDEN)


def _una_por_pose(candidatas: List[Dict[str, Any]], fecha: str) -> List[Dict[str, Any]]:
    """De las fotos cercanas a un día, la más próxima de cada pose (si dos sesiones caen
    en la ventana, no se enseñan seis fotos: una por ángulo)."""
    por_pose: Dict[Any, List[Dict[str, Any]]] = {}
    for f in candidatas:
        por_pose.setdefault(f.get("pose"), []).append(f)
    elegidas = [_mas_cercano(fotos, fecha, None) for fotos in por_pose.values()]
    elegidas = [f for f in elegidas if f]
    elegidas.sort(key=lambda f: (_orden_de_pose(f.get("pose")), f.get("taken_at") or ""))
    return [_foto_breve(f) for f in elegidas]


def _fotos_del_reporte(reporte: Dict[str, Any], fecha: str, fotos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Las fotos cosidas al reporte (`report_id` en la foto, o su id en `photos` del
    reporte) y, si no tiene ninguna (todos los de antes del 4-09, y los de Calma), las
    subidas a una semana del reporte que no sean de otro reporte, una por pose."""
    ids = set(f for f in (reporte.get("photos") or []) if f)
    propias = [f for f in fotos if f.get("report_id") == reporte["id"] or f.get("id") in ids]
    if propias:
        propias.sort(key=lambda f: (_orden_de_pose(f.get("pose")), f.get("taken_at") or ""))
        return [_foto_breve(f) for f in propias]
    cerca = [f for f in fotos
             if not f.get("report_id") and f.get("fecha") and _distancia(f["fecha"], fecha) <= DIAS_DE_MARGEN_HITO]
    return _una_por_pose(cerca, fecha)


# ==================== marcas y atajos de fotos y tomas ====================

def _marcar_inicio_y_final(elementos: List[Dict[str, Any]], grupos: _Grupos) -> None:
    """A cada foto (o toma) su `marca`: «inicio» las del día más cercano al arranque de su
    grupo (a una semana como mucho), «final» las del día más cercano a su fin. Se marca el
    DÍA entero porque una toma son tres fotos del mismo día."""
    por_grupo: Dict[str, List[Dict[str, Any]]] = {}
    for e in elementos:
        e["marca"] = None
        por_grupo.setdefault(e["grupo"]["id"], []).append(e)
    for gid, lista in por_grupo.items():
        g = grupos.por_id.get(gid)
        if not g:
            continue
        candidatos = [{"fecha": d} for d in sorted({e["fecha"] for e in lista})]
        inicio = _mas_cercano(candidatos, g["inicio"], DIAS_DE_MARGEN_HITO)
        final = _mas_cercano(candidatos, g["fin_efectivo"], DIAS_DE_MARGEN_HITO) if g.get("fin_efectivo") else None
        for e in lista:
            if inicio and e["fecha"] == inicio["fecha"]:
                e["marca"] = "inicio"
            elif final and e["fecha"] == final["fecha"]:
                e["marca"] = "final"


def _elegir_del_dia(elementos: List[Dict[str, Any]], fecha: str, con_pose: bool):
    """De lo que hay ese día, la foto de frente si la hay (si no, la que haya y se dice);
    para las tomas de medidas no hay ángulo y va la primera."""
    del_dia = [e for e in elementos if e["fecha"] == fecha]
    if not del_dia:
        return None, None
    if not con_pose:
        return del_dia[0], None
    de_frente = next((e for e in del_dia if e.get("pose") == POSE_QUE_MANDA), None)
    if de_frente:
        return de_frente, None
    del_dia.sort(key=lambda e: _orden_de_pose(e.get("pose")))
    return del_dia[0], "no tienes foto de frente de esa fecha"


def _atajo_a(elementos: List[Dict[str, Any]], hito: Optional[str], que: str, hoy: str,
             con_pose: bool) -> Optional[Dict[str, Any]]:
    """El elemento más cercano a un hito, con nota si está a más de una semana («la más
    próxima al inicio del ciclo: 12 de junio») o si no es de frente. None sin hito o sin
    nada que elegir: el front lo enseña apagado."""
    if not hito or not elementos:
        return None
    dias = sorted({e["fecha"] for e in elementos})
    cercano = _mas_cercano([{"fecha": d} for d in dias], hito, None)
    if not cercano:
        return None
    elegido, nota_pose = _elegir_del_dia(elementos, cercano["fecha"], con_pose)
    notas = []
    if _distancia(cercano["fecha"], hito) > DIAS_DE_MARGEN_HITO:
        notas.append(f"la más próxima {que}: {_en_palabras(cercano['fecha'], hoy)}")
    if nota_pose:
        notas.append(nota_pose)
    return {"id": elegido["id"], "nota": ". ".join(notas) if notas else None}


def _atajos_de(elementos: List[Dict[str, Any]], grupos: _Grupos, hoy: str, con_pose: bool) -> Dict[str, Any]:
    """Los cuatro atajos del selector (doc del 2-09: mi primera foto · inicio de este
    ciclo · fin del ciclo anterior · hoy), iguales para fotos y para tomas de medidas.
    `mi_primera_foto` y `hoy` van como id a secas (contrato del 4-09) y su nota, si la
    hay, al lado en `*_nota`; `mi_primera_toma` es el mismo atajo con nombre de medidas."""
    vacio = {"mi_primera_foto": None, "mi_primera_foto_nota": None, "mi_primera_toma": None,
             "inicio_de_este_ciclo": None, "fin_del_ciclo_anterior": None,
             "hoy": None, "hoy_nota": None}
    if not elementos:
        return vacio
    primera, nota_primera = _elegir_del_dia(elementos, elementos[0]["fecha"], con_pose)
    ultima, nota_ultima = _elegir_del_dia(elementos, elementos[-1]["fecha"], con_pose)
    abierto = grupos.abierto()
    anterior = grupos.anterior_al_abierto()
    return {
        "mi_primera_foto": primera["id"], "mi_primera_foto_nota": nota_primera,
        "mi_primera_toma": primera["id"],
        "inicio_de_este_ciclo": _atajo_a(elementos, abierto["inicio"] if abierto else None,
                                         "al inicio del ciclo", hoy, con_pose),
        "fin_del_ciclo_anterior": _atajo_a(elementos, anterior["fin"] if anterior else None,
                                           "al final del ciclo anterior", hoy, con_pose),
        "hoy": ultima["id"], "hoy_nota": nota_ultima,
    }


# ==================== la composición ====================

def _filas_de_macros(crudas: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Una fila por día de vigencia (la guardada más tarde manda, como en «Mis macros»),
    de la más antigua a la más nueva."""
    por_dia: Dict[str, Dict[str, Any]] = {}
    for h in crudas:
        dia = fecha_de_vigencia(h)
        if not dia:
            continue
        previa = por_dia.get(dia)
        if not previa or str(h.get("created_at") or "") >= str(previa.get("created_at") or ""):
            por_dia[dia] = {**h, "fecha": dia}
    return [por_dia[d] for d in sorted(por_dia)]


def _serie_de_grasa(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    serie = []
    for p in (profile.get("porcentajes_grasos") or []):
        dia = dia_de_espana(p.get("fecha"))
        try:
            valor = round(float(p.get("valor")), 1)
        except (TypeError, ValueError):
            continue
        if dia:
            serie.append({"fecha": dia, "valor": valor})
    serie.sort(key=lambda p: p["fecha"])
    return serie


async def _cargar(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Todo lo que hace falta, en una pasada. Lo secundario (cuaderno, fotos) no puede
    tumbar la lista: si falla, va vacío y el detalle a consola."""
    client_id = profile.get("id")
    user_id = profile.get("user_id")
    cuaderno: List[Dict[str, Any]] = []
    fotos: List[Dict[str, Any]] = []
    fotos_alta: List[Dict[str, Any]] = []
    if client_id:
        try:
            cuaderno = await ciclos_de(client_id)
        except Exception as e:      # noqa: BLE001
            logger.warning("puntos de %s sin cuaderno de ciclos: %s", client_id, e)
        try:
            # La MISMA lista (y la misma `url` firmada) que GET /reports/photos: el listado
            # busca por user_id o por client_id, así que basta con el id del usuario.
            fotos = await listar_fotos_de({"id": user_id})
        except Exception as e:      # noqa: BLE001
            logger.warning("puntos de %s sin fotos: %s", client_id, e)
        try:
            # Las del alta (con `uso`: la del carrusel de grasa y la de su mejor forma) no
            # son de progreso y el listado las deja fuera; aquí solo entran en el Punto 0.
            fotos_alta = await db.client_photos.find(
                {"client_id": client_id, "uso": {"$exists": True}}, {"_id": 0, "data": 0}
            ).sort("taken_at", 1).to_list(50)
        except Exception as e:      # noqa: BLE001
            logger.warning("puntos de %s sin fotos del alta: %s", client_id, e)
    reportes = await db.reports.find(
        hasta_hoy({"client_id": client_id}), _PROYECCION_REPORTE).sort("created_at", 1).to_list(3000)
    macros = await db.macro_history.find({"client_id": client_id}, _PROYECCION_MACROS).to_list(3000)
    return {"cuaderno": cuaderno, "fotos": fotos, "fotos_alta": fotos_alta,
            "reportes": reportes, "macros": _filas_de_macros(macros)}


async def puntos_de(profile: Dict[str, Any]) -> Dict[str, Any]:
    """La respuesta entera de `GET /reports/puntos` y `GET /admin/clients/{id}/puntos`:
    los ciclos (y tramos), los puntos con sus etiquetas y atajos, las fotos y las tomas
    de medidas del selector con sus grupos, marcas y atajos. Sin pedirle nada al front."""
    profile = profile or {}
    hoy = hoy_madrid().isoformat()
    datos = await _cargar(profile)

    # ── Las fotos con su día de España, de la más antigua a la de hoy (en toda la pantalla
    # el tiempo va en la misma dirección), y sin las de mañana.
    fotos: List[Dict[str, Any]] = []
    for f in datos["fotos"]:
        fecha = dia_de_espana(f.get("taken_at"))
        if fecha and fecha <= hoy:
            fotos.append({**f, "fecha": fecha})
    fotos.sort(key=lambda f: (f["fecha"], str(f.get("taken_at") or "")))
    fotos_alta = []
    for f in datos["fotos_alta"]:
        fecha = dia_de_espana(f.get("taken_at"))
        if fecha and fecha <= hoy:
            fotos_alta.append({**f, "fecha": fecha, "ref": f.get("id"), "fuente": "app"})

    # ── Los reportes que son punto, con su día.
    reportes = []
    for r in datos["reportes"]:
        if r.get("tipo") not in TIPOS_QUE_SON_PUNTO:
            continue
        fecha = _dia_del_reporte(r)
        if fecha and fecha <= hoy:
            reportes.append({**r, "fecha": fecha})
    reportes.sort(key=lambda r: (r["fecha"], str(r.get("created_at") or "")))

    # ── Las tres puertas de las medidas, como tomas sueltas (sin grupo todavía).
    tomas: List[Dict[str, Any]] = []
    for r in datos["reportes"]:
        medidas = _medidas_limpias(r.get("measurements"))
        fecha = _dia_del_reporte(r)
        if medidas and fecha and fecha <= hoy:
            tomas.append({"id": r["id"], "fecha": fecha, "origen": "reporte", "measurements": medidas,
                          "_ciclo_id": r.get("ciclo_id")})
    for t in (profile.get("medidas_sueltas") or []):
        medidas = _medidas_limpias(t.get("measurements"))
        fecha = dia_de_espana(t.get("fecha"))
        if medidas and fecha and fecha <= hoy:
            tomas.append({"id": f"suelta:{fecha}", "fecha": fecha, "origen": "suelta",
                          "measurements": medidas, "_ciclo_id": None})
    medidas_inicio = profile.get("medidas_inicio") or {}
    fecha_inicio = dia_de_espana(medidas_inicio.get("fecha")) if isinstance(medidas_inicio, dict) else None
    medidas_del_inicio = _medidas_limpias(medidas_inicio)
    if fecha_inicio and medidas_del_inicio and fecha_inicio <= hoy:
        tomas.append({"id": "inicio", "fecha": fecha_inicio, "origen": "inicio",
                      "measurements": medidas_del_inicio, "_ciclo_id": None})
    tomas.sort(key=lambda t: (t["fecha"], t["origen"]))

    # ── El ancla de los tramos aproximados: el alta, o lo primero que haya si es anterior.
    candidatas = [dia_de_espana(profile.get("created_at"))]
    candidatas += [r["fecha"] for r in reportes] + [f["fecha"] for f in fotos] + [t["fecha"] for t in tomas]
    candidatas = [c for c in candidatas if c]
    grupos = _Grupos(profile, datos["cuaderno"], min(candidatas) if candidatas else None, hoy)

    curva = curva_de_peso(profile.get("pesos"), datos["macros"])       # [{fecha, peso}]
    grasa = _serie_de_grasa(profile)                                    # [{fecha, valor}]
    macros = datos["macros"]

    # ── Los puntos: uno por reporte mensual.
    puntos: List[Dict[str, Any]] = []
    for r in reportes:
        g = grupos.de(r["fecha"], r.get("ciclo_id"))
        semana, bloque = _semana_y_bloque(g, r["fecha"], r.get("semana_del_ciclo"), r.get("bloque"))
        que = "Tramo" if g["aproximado"] else "Ciclo"
        if bloque < g["bloques"]:
            secundario = f"y el inicio del bloque {bloque + 1}"
        else:
            secundario = f"y el final del {que.lower()} {g['numero']}"
        puntos.append({
            "id": r["id"], "tipo": "reporte", "fecha": r["fecha"], "report_id": r["id"],
            "ciclo_id": None if g["aproximado"] else g["id"], "ciclo_numero": g["numero"],
            "semana": semana, "bloque": bloque, "aproximado": g["aproximado"],
            "nombre": f"Final bloque {bloque} · {que} {g['numero']}",
            "nombre_secundario": secundario,
            "objetivo": g["objetivo"], "objetivo_nombre": g["objetivo_nombre"],
            "peso": sanea_peso(r.get("weight")),
            "medidas": _medidas_limpias(r.get("measurements")),
            "grasa": _valor_cercano(grasa, r["fecha"], "valor"),
            "macros": _macros_vigentes(macros, r["fecha"]),
            "fotos": _fotos_del_reporte(r, r["fecha"], fotos),
            "etiquetas": [],
        })

    # ── El Punto 0 de cada ciclo que arranca sin un reporte pegado.
    for g in grupos.cuaderno:
        if g["motivo"] not in MOTIVOS_CON_PUNTO_0 or g["inicio"] > hoy:
            continue
        if any(_distancia(p["fecha"], g["inicio"]) <= DIAS_DE_MARGEN_HITO for p in puntos if p["tipo"] == "reporte"):
            continue
        es_alta = g["motivo"] in ("alta", "registro_inicial")
        cerca = [f for f in fotos if not f.get("report_id") and _distancia(f["fecha"], g["inicio"]) <= DIAS_DE_MARGEN_HITO]
        if es_alta:
            # Las del alta son de ese arranque aunque las subiera unos días antes de pagar.
            cerca = fotos_alta + cerca
        medidas = None
        if fecha_inicio and medidas_del_inicio and _distancia(fecha_inicio, g["inicio"]) <= DIAS_DE_MARGEN_HITO:
            medidas = medidas_del_inicio
        puntos.append({
            "id": f"punto0:{g['id']}", "tipo": "punto0", "fecha": g["inicio"], "report_id": None,
            "ciclo_id": g["id"], "ciclo_numero": g["numero"], "semana": 1, "bloque": 1,
            "aproximado": False,
            "nombre": f"Punto 0 · Ciclo {g['numero']}",
            "nombre_secundario": "el alta" if es_alta else "la vuelta",
            "objetivo": g["objetivo"], "objetivo_nombre": g["objetivo_nombre"],
            "peso": _valor_cercano(curva, g["inicio"], "peso"),
            "medidas": medidas,
            "grasa": _valor_cercano(grasa, g["inicio"], "valor"),
            "macros": _macros_vigentes(macros, g["inicio"]),
            "fotos": _una_por_pose(cerca, g["inicio"]),
            "etiquetas": [],
        })
    puntos.sort(key=lambda p: (p["fecha"], 0 if p["tipo"] == "punto0" else 1))

    # ── Las etiquetas. Peso máximo y mínimo salen solas sobre los pesos de los puntos, una
    # cada una y en empate la más antigua (max/min devuelven la primera); con un solo peso
    # no hay máximo ni mínimo que valga. El pico de forma lo marca el entrenador en el
    # cuaderno, uno por ciclo, y «no es el peso mínimo».
    con_peso = [p for p in puntos if p["peso"] is not None]
    id_maximo = id_minimo = None
    if len(con_peso) >= 2:
        id_maximo = max(con_peso, key=lambda p: p["peso"])["id"]
        id_minimo = min(con_peso, key=lambda p: p["peso"])["id"]
    picos = {g["pico_de_forma"] for g in grupos.cuaderno if g.get("pico_de_forma")}
    por_id = {p["id"]: p for p in puntos}
    for p in puntos:
        if p["report_id"] and p["report_id"] in picos:
            p["etiquetas"].append("pico_de_forma")
        if p["id"] == id_maximo:
            p["etiquetas"].append("peso_maximo")
        if p["id"] == id_minimo:
            p["etiquetas"].append("peso_minimo")

    abierto = grupos.abierto()
    if abierto and abierto.get("pico_de_forma") in por_id:
        pico_id = abierto["pico_de_forma"]
    else:
        # Sin pico en el ciclo abierto, el último que se marcó.
        con_pico = [p for p in puntos if "pico_de_forma" in p["etiquetas"]]
        pico_id = con_pico[-1]["id"] if con_pico else None
    inicio_de_este_ciclo = None
    if abierto and puntos:
        cercano = _mas_cercano(puntos, abierto["inicio"], None)
        nota = None
        if _distancia(cercano["fecha"], abierto["inicio"]) > DIAS_DE_MARGEN_HITO:
            nota = f"el más próximo al inicio del ciclo: {_en_palabras(cercano['fecha'], hoy)}"
        inicio_de_este_ciclo = {"id": cercano["id"], "nota": nota}
    atajos_puntos = {
        "pico_de_forma": pico_id, "peso_maximo": id_maximo, "peso_minimo": id_minimo,
        "inicio_de_este_ciclo": inicio_de_este_ciclo,
        "hoy": puntos[-1]["id"] if puntos else None,
    }

    # ── El selector de fotos: todas las de progreso, con su grupo y su marca.
    fotos_selector = []
    for f in fotos:
        g = grupos.de(f["fecha"], f.get("ciclo_id"))
        fotos_selector.append({**_foto_breve(f), "report_id": f.get("report_id"), "grupo": _Grupos.breve(g)})
    _marcar_inicio_y_final(fotos_selector, grupos)
    atajos_fotos = _atajos_de(fotos_selector, grupos, hoy, con_pose=True)

    # ── El selector de tomas de medidas, igual.
    tomas_selector = []
    for t in tomas:
        g = grupos.de(t["fecha"], t.pop("_ciclo_id", None))
        tomas_selector.append({**t, "grupo": _Grupos.breve(g)})
    _marcar_inicio_y_final(tomas_selector, grupos)
    atajos_medidas = _atajos_de(tomas_selector, grupos, hoy, con_pose=False)

    return {
        "hoy": hoy,
        "ciclos": [_Grupos.para_la_lista(g) for g in grupos.todos()],
        "puntos": puntos,
        "atajos_puntos": atajos_puntos,
        "fotos": fotos_selector,
        "atajos_fotos": atajos_fotos,
        "tomas_medidas": tomas_selector,
        "atajos_medidas": atajos_medidas,
    }
