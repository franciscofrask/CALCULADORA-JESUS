# -*- coding: utf-8 -*-
"""
Seccion C de la lista de 85 casos de prueba de Jesus: NUTRICION Y CONFIGURACION DEL DIA
(casos 11 a 20). Se prueba lo que el pide, con sus palabras, y donde de verdad vive:

  11-14 y 19  la pantalla de Nutricion (`frontend/src/pages/NutritionPage.jsx` y su
              cabecera `components/nutrition/DayHeader.jsx`). El titular del dia
              ("Hoy tienes que comer", "Te queda por comer", "Te has pasado", "Dia
              cuadrado") lo decide el FRONT, no el backend: la cuenta de lo que falta
              es `tgt - val` dentro de DayHeader. Por eso esos casos no se pueden pedir
              por HTTP.

              No se reescribe esa logica en Python -- una copia no prueba nada --: se
              SACAN LAS LINEAS DEL PROPIO FICHERO y se ejecutan con node. Si alguien
              cambia el titular o quita el tope del cero, estos tests se enteran.

  15-18       el reparto de macros por comida, `backend/macro_distribution.py::distribuir_macros`.
              Es una funcion pura: se llama directamente, sin base de datos ni HTTP.

  20          `backend/macros_por_fecha.py`: los macros de un dia salen del ajuste
              VIGENTE a esa fecha (`macro_history.effective_date`), no de los de hoy.
              Se prueba con un doble de la base y, ademas, contra el backend vivo con
              el historial real del cliente demo.

Ejecutar:
    cd backend && REACT_APP_BACKEND_URL=http://localhost:8000 \
        venv/Scripts/python.exe -m pytest tests/test_casos_C_nutricion.py -q
"""
import asyncio
import json
import logging
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest
import requests

from conftest import API
from macro_distribution import distribuir_macros
from macros_por_fecha import elegir_entrada, resolver


def correr(coro):
    """No hay pytest-asyncio en el repo: se corre a mano, como en el resto de tests."""
    return asyncio.run(coro)


RAIZ = pathlib.Path(__file__).resolve().parents[2]
DAY_HEADER = RAIZ / "frontend" / "src" / "components" / "nutrition" / "DayHeader.jsx"
MEAL_CARD = RAIZ / "frontend" / "src" / "components" / "nutrition" / "MealCard.jsx"
NUTRITION_PAGE = RAIZ / "frontend" / "src" / "pages" / "NutritionPage.jsx"


# =====================================================================================
# CASOS 11-14: EL TITULAR DEL DIA, EJECUTANDO EL CODIGO QUE HAY EN DayHeader.jsx
# =====================================================================================

# LA CABECERA YA NO DECIDE NADA POR SU CUENTA (puntos 105 a 107 del artifact del 25-08).
# Hasta el 26-08 el titular y el numero grande se calculaban con lineas sueltas dentro del
# JSX, y este harness las recortaba del fichero para ejecutarlas. Ahora la regla vive
# entera en `lib/estadoDelMacro`, la misma que usa Inicio, asi que se lleva el modulo DE
# VERDAD y se llama a `leerMacro`: si manana cambia el margen o una palabra, esto se entera.
_PLANTILLA_JS = r"""
import { leerMacro } from './estadoDelMacro.mjs';
const casos = %(casos)s;
const salida = casos.map((macros) => {
  const numeros = {}, palabras = {}, colores = {};
  for (const m of macros) {
    // EL NUMERO ES SIEMPRE LO CREADO. Antes era lo que FALTA mientras ibas a medias y
    // pasaba a ser lo servido al cuadrar o al pasarte: dos magnitudes en el mismo hueco.
    numeros[m.key] = Math.round(m.valDia);
    const l = leerMacro({ vista: 'dieta', hay: m.valDia, objetivo: m.tgtDia });
    palabras[m.key] = l.palabra;
    colores[m.key] = l.color;
  }
  return { numeros, palabras, colores };
});
// A ASCII: las palabras llevan tilde ("valido +2") y la consola de Windows no siempre la
// deja pasar entera. Con las escapadas uXXXX el JSON viaja igual en cualquier consola.
console.log(JSON.stringify(salida).replace(/./gu, (c) => {
  const n = c.codePointAt(0);
  return n > 126 ? String.fromCharCode(92) + "u" + n.toString(16).padStart(4, "0") : c;
}));
"""


def _llevar_modulo(destino, nombre):
    """Copia un modulo de `frontend/src/lib` al lado del harness, para node.

    El bloque del titular llama a `seExcede` y a `textoExceso`, que viven en
    `lib/exceso.js` (el criterio de «pasarse», en un solo sitio desde el 13-08). Un doble
    escrito aqui no probaria nada: si manana cambia el margen, el test seguiria en verde
    con la regla vieja. Asi que se lleva el fichero DE VERDAD; lo unico que se toca es la
    extension de los imports relativos, que webpack se la inventa y node la exige.
    """
    fuente = RAIZ / "frontend" / "src" / "lib" / f"{nombre}.js"
    texto = fuente.read_text(encoding="utf-8")
    texto = re.sub(r"(from\s+['\"]\./)([\w/-]+)(['\"])", r"\1\2.mjs\3", texto)
    (destino / f"{nombre}.mjs").write_text(texto, encoding="utf-8")


def _el_numero_grande_es_lo_creado():
    """Que el JSX siga pintando lo CREADO y no otra cosa. La regla la prueba `leerMacro`,
    pero QUE numero se pinta solo lo dice la cabecera, y es la mitad del punto 106."""
    texto = DAY_HEADER.read_text(encoding="utf-8")
    assert "const creado = Math.round(valDia);" in texto, \
        "el numero grande de Nutricion ha dejado de ser lo creado: vuelve a cambiar de criterio"
    assert 'data-testid="dia-titular"' not in texto, \
        "vuelve el titular que rotaba entre cuatro frases (punto 106)"


@pytest.fixture(scope="module")
def lectura_de():
    """Devuelve una funcion que lee los macros del dia tal como los pinta la cabecera."""
    if not shutil.which("node"):
        pytest.skip("hace falta node para ejecutar la regla tal cual esta en lib/estadoDelMacro.js")
    _el_numero_grande_es_lo_creado()

    def _evaluar(*casos):
        js = _PLANTILLA_JS % {"casos": json.dumps(list(casos))}
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = pathlib.Path(tmp)
            for modulo in ("numeros", "exceso", "estadoDelMacro"):
                _llevar_modulo(carpeta, modulo)
            fichero = carpeta / "lectura.mjs"
            fichero.write_text(js, encoding="utf-8")
            salida = subprocess.run(["node", str(fichero)], capture_output=True, text=True)
        assert salida.returncode == 0, f"node fallo: {salida.stderr}"
        return json.loads(salida.stdout)

    return _evaluar


def macro(key, val, tgt, val_dia=None, tgt_dia=None):
    """Un macro tal como lo recibe la cabecera.

    `val`/`tgt` son el dia SIN el perientreno (con eso decide si te has pasado) y
    `valDia`/`tgtDia` el dia ENTERO, que es de donde sale el numero grande. En estos
    casos no hay peri, asi que por defecto son lo mismo; se pueden separar para probarlo.
    """
    return {"key": key, "val": val, "tgt": tgt,
            "valDia": val if val_dia is None else val_dia,
            "tgtDia": tgt if tgt_dia is None else tgt_dia}


# Objetivo de las comidas del cliente demo (dia de entreno, sin contar el perientreno,
# que la cabecera lleva por su cuenta): 190 P, 135 H, 60 G.
OBJETIVO = [macro("P", 0, 190), macro("H", 0, 135), macro("G", 0, 60)]


def _con_comido(p, h, g):
    return [macro("P", p, 190), macro("H", h, 135), macro("G", g, 60)]


def test_11_el_dia_a_cero_dice_lo_que_hay_que_comer(lectura_de):
    """Caso 11: con el dia a cero, el cliente sabe lo que tiene que comer.

    Lo decia un titular, «Hoy tienes que comer», con los tres numeros del objetivo debajo.
    Desde el 26-08 el numero es SIEMPRE lo creado -- a cero, cero -- y lo que hay que comer
    lo dice la palabra de cada macro: «faltan 190». Mismo dato, sin cambiar de magnitud a
    mitad de dia (puntos 105 a 107 del artifact del 25-08).
    """
    r = lectura_de(OBJETIVO)[0]
    assert r["numeros"] == {"P": 0, "H": 0, "G": 0}, "el numero es lo creado, y a cero no hay nada"
    assert r["palabras"] == {"P": "faltan 190", "H": "faltan 135", "G": "faltan 60"}


def test_12_con_una_comida_montada_resta_lo_comido(lectura_de):
    """Caso 12 [CRITICO]: resta lo comido, no lo suma.

    El numero es ahora lo creado, asi que la resta que hay que vigilar es la de la palabra:
    con 47 de 190 tienen que faltar 143, no 237.
    """
    r = lectura_de(_con_comido(47, 51, 12))[0]
    assert r["numeros"] == {"P": 47, "H": 51, "G": 12}, "el numero es lo que llevas creado"
    assert r["palabras"] == {"P": "faltan 143", "H": "faltan 84", "G": "faltan 48"}, \
        "tiene que restar lo comido, no sumarlo"


def test_13_pasarse_de_un_macro_lo_dice(lectura_de):
    """Caso 13 [CRITICO]: pasarse se dice, y en el macro en el que pasa."""
    r = lectura_de(_con_comido(200, 175, 62))[0]
    assert r["palabras"]["H"] == "sobran 40"
    assert r["colores"]["H"] == "pasado", "pasarse tiene que pintar"


def test_13_nunca_sale_un_numero_negativo(lectura_de):
    """Caso 13 [CRITICO]: nunca un «faltan -8 H».

    Con el numero a lo creado el negativo ya no puede salir por ahi, pero si podria salir
    en la palabra si alguien restara al reves. Se comprueban los dos.
    """
    casos = [
        _con_comido(200, 175, 62),     # pasado de largo
        _con_comido(193, 138, 63),     # pasado de poco: 3 g por encima en los tres
        _con_comido(190, 143, 60),     # solo un macro, y por poco
        _con_comido(400, 400, 400),    # el doble de todo
        _con_comido(0, 0, 0),          # sin empezar
    ]
    for entrada, r in zip(casos, lectura_de(*casos)):
        for clave, valor in r["numeros"].items():
            assert valor >= 0, f"numero negativo en {clave} con {entrada}: {r}"
        for clave, palabra in r["palabras"].items():
            assert "-" not in palabra and "\u2212" not in palabra.replace("\u2212", "", 1), \
                f"palabra con signo raro en {clave} con {entrada}: {palabra!r}"


def test_13_dice_por_cuanto_se_ha_pasado(lectura_de):
    """Caso 13, la otra mitad: «dice "te has pasado" Y POR CUANTO».

    Antes lo decia una frase al lado del titular, sacada de `lib/exceso`. Ahora lo dice
    cada macro debajo de su numero, que es donde se mira: «sobran 40».

    OJO, UNA REGLA VIEJA QUE AQUI YA NO SE APLICA. Hasta el 26-08 pasarse de PROTEINA no
    se cantaba (Jesus, 13-08: «le estas marcando en rojo, todos los dias, algo que ha hecho
    bien»), y `lib/exceso` sigue teniendolo asi (`MACROS_QUE_SE_PASAN = ['H','G']`). La
    regla de color de la parte 2 no distingue macros -- «igual en las cuatro pestañas, sin
    excepciones» -- y la parte 3 manda usar esa, asi que con 200 de 190 la proteina TAMBIEN
    dice «sobran 10». Esta preguntado a Jesus; si dice que la excepcion se queda, se cambia
    en `lib/estadoDelMacro` y este test lo cazara.
    """
    r = lectura_de(_con_comido(200, 175, 62))[0]
    assert r["palabras"]["H"] == "sobran 40", "no dice por cuanto se ha pasado"
    # La grasa, 2 g por encima, cabe en el margen de 4 de Calma y no es un aviso.
    #
    # LA PALABRA CAMBIO EL 2-09 y el estado no: dentro del margen decia «valido +2», que era
    # una cuarta palabra para el mismo eje («cuadrado», «valido», «faltan», «sobran») y no
    # decia si faltaba o sobraba. Ahora dice «cuadrado (+2)»: la misma familia que el
    # cuadrado de verdad, con el desvio pequeno entre parentesis. El color sigue en verde,
    # que es lo que este caso comprueba de verdad.
    assert r["palabras"]["G"].startswith("cuadrado ("), r["palabras"]["G"]
    assert "+2" in r["palabras"]["G"], r["palabras"]["G"]
    assert r["colores"]["G"] == "ok", "2 g caben en el margen: eso no es pasarse"
    assert r["palabras"]["P"] == "sobran 10", \
        "si esto cambia es que se ha devuelto la excepcion de la proteina: mira el docstring"


def test_14_el_dia_cuadrado_lo_dice(lectura_de):
    """Caso 14: cuadrar el dia entero se ve, ahora en los tres macros a la vez."""
    r = lectura_de(_con_comido(190, 135, 60))[0]
    assert r["palabras"] == {"P": "cuadrado", "H": "cuadrado", "G": "cuadrado"}
    assert set(r["colores"].values()) == {"ok"}, "los tres en verde son el dia cuadrado"


def test_14_el_boton_grande_de_montar_solo_sale_con_la_comida_vacia():
    """Caso 14, la otra mitad: con el dia cuadrado desaparece el boton grande de montar.

    El boton grande es "Sugiereme un menu" (`btn-brand`, el CTA del estado vacio de cada
    comida) y esta atado a `foods.length === 0`: con el dia cuadrado ninguna comida esta
    vacia, asi que no queda ninguno en pantalla. Se comprueba sobre el codigo porque
    montar el arbol de React desde pytest cuesta mas de lo que aporta.
    """
    texto = MEAL_CARD.read_text(encoding="utf-8")
    assert "foods.length === 0 && !isPeri && !isLocked" in texto, \
        "el estado vacio de la comida ya no depende de que este vacia: revisa el caso 14"
    assert "foods.length === 0 && isPeri && !isLocked" in texto, \
        "lo mismo para el intra/post"


# =====================================================================================
# CASOS 15-18: EL REPARTO POR COMIDA (funcion pura, sin base de datos)
# =====================================================================================

# Los macros del cliente demo, que son los que se ven al probar a mano.
DEMO = dict(p_entreno=190.0, h_entreno=170.0, g_entreno=60.0,
            p_peri=45.0, h_peri=50.0,
            p_descanso=225.0, h_descanso=170.0, g_descanso=60.0)


def repartir(**cambios):
    args = dict(DEMO, tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
                opcion_peri="intra_post")
    args.update(cambios)
    return distribuir_macros(**args)


def suma(resultado, macro_):
    """Lo que suman las COMIDAS (sin el peri, que va aparte)."""
    return round(sum(c[macro_] for c in resultado["comidas"].values()), 1)


def totales(resultado):
    r = resultado["resumen"]
    return (r["P_total"], r["H_total"], r["G_total"])


def test_15_de_4_a_3_comidas_se_recoloca_pero_el_dia_no_cambia():
    """Caso 15 [CRITICO]: cambiar de 4 a 3 comidas recoloca el reparto, no el total."""
    r4 = repartir(num_comidas=4)
    r3 = repartir(num_comidas=3)

    assert len(r3["comidas"]) == 3 and len(r4["comidas"]) == 4
    for a, b in zip(totales(r3), totales(r4)):
        assert a == pytest.approx(b, abs=0.4), "el total del dia no puede moverse por partirlo distinto"
    # Y el reparto SI se recoloca: con 3 va a tercios, con 4 manda la tabla del escenario.
    assert r3["comidas"]["C1"] != r4["comidas"]["C1"]
    assert r3["comidas"]["C1"] == r3["comidas"]["C3"], "3 comidas reparten a tercios"


def test_15_el_peri_sigue_intacto_al_cambiar_el_numero_de_comidas():
    """El intra/post no depende de cuantas comidas haya: es presupuesto aparte."""
    assert repartir(num_comidas=3)["periworkout"] == repartir(num_comidas=4)["periworkout"]


def test_16_de_entreno_a_descanso_cambian_los_macros_del_dia():
    """Caso 16 [CRITICO]: el dia de descanso usa SUS macros, no los de entreno."""
    ent = repartir(tipo_dia="entrenamiento")
    des = repartir(tipo_dia="descanso")

    assert totales(des) == (DEMO["p_descanso"], DEMO["h_descanso"], DEMO["g_descanso"])
    assert totales(des) != totales(ent), "si no cambia nada, el conmutador no sirve de nada"
    assert des["periworkout"] == {}, "un dia de descanso no lleva perientreno"
    # Descanso reparte a partes iguales entre las comidas que haya.
    comidas = list(des["comidas"].values())
    assert all(c == comidas[0] for c in comidas)


def test_16_al_cliente_se_le_avisa_de_que_sus_macros_cambian():
    """Caso 16, la otra mitad: "y lo avisa".

    Desde el punto 8 del doc del 23-08 la frase «¿Este dia entrenas o descansas? Tus
    macros cambian» esta FUERA (y sin sustituto): el aviso es el aro naranja del
    conmutador (`diaSinMarcar`), en el sitio donde se actua. Aqui se fija que el aro
    sigue y que la frase no vuelve por la puerta de atras.
    """
    texto = DAY_HEADER.read_text(encoding="utf-8")
    assert "Tus macros cambian" not in texto, \
        "la frase del conmutador volvio: el punto 8 del 23-08 la quito a proposito"
    assert "diaSinMarcar ? 'ring-2 ring-brand" in texto, \
        "se ha perdido el aro del conmutador, que es el unico aviso que queda"


def test_17_marcar_y_desmarcar_el_perientreno_no_altera_el_total():
    """Caso 17 [CRITICO]: quitar el peri reparte su parte entre las comidas, sin tocar el total."""
    con = repartir(opcion_peri="intra_post")
    sin = repartir(opcion_peri="sin_peri")

    assert "Intra" in con["periworkout"] and "Post" in con["periworkout"]
    assert sin["periworkout"] == {}, "sin peri no hay ni intra ni post"

    for a, b in zip(totales(sin), totales(con)):
        assert a == pytest.approx(b, abs=0.4), "el total del dia no cambia por como te tomes el peri"

    # Su parte se reparte EN LAS COMIDAS: 45 P y 50 H mas que con intra/post.
    assert suma(sin, "P") == pytest.approx(suma(con, "P") + DEMO["p_peri"], abs=0.4)
    assert suma(sin, "H") == pytest.approx(suma(con, "H") + DEMO["h_peri"], abs=0.4)
    assert suma(sin, "G") == pytest.approx(suma(con, "G"), abs=0.4), "el peri no lleva grasa"


def test_17_solo_intra_deja_en_las_comidas_lo_que_no_se_bebe():
    """Los otros dos modos del peri, que son oficiales aunque no existan en Calma."""
    solo_intra = repartir(opcion_peri="solo_intra")
    solo_post = repartir(opcion_peri="solo_post")

    assert "Post" not in solo_intra["periworkout"]
    assert solo_intra["periworkout"]["Intra"]["P"] == pytest.approx(DEMO["p_peri"] * 0.25, abs=0.1)
    # El 75 % restante se lo comen las comidas.
    assert suma(solo_intra, "P") == pytest.approx(190 + DEMO["p_peri"] * 0.75, abs=0.4)

    assert "Intra" not in solo_post["periworkout"]
    assert solo_post["periworkout"]["Post"]["P"] == pytest.approx(DEMO["p_peri"], abs=0.1)


def test_17_un_modo_de_peri_desconocido_cae_en_intra_post_y_lo_dice(caplog):
    """Los cuatro modos, y nada mas. Corregir en silencio deja al cliente con otro reparto."""
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        r = repartir(opcion_peri="lo_que_sea")
    assert r["config"]["opcion_peri"] == "intra_post"
    assert any("opcion_peri" in m for m in caplog.messages), "se corrigio sin avisar"


@pytest.mark.parametrize("momento", [0, 1, 2, 3])
def test_18_las_comidas_se_recolocan_alrededor_del_entreno(momento):
    """Caso 18: cambiar el momento del entreno recoloca el reparto.

    Con pocos hidratos (escenario 4) se ve sin ambiguedad: los hidratos van a la comida de
    DESPUES del entreno. Momento 0 (en ayunas) -> C1; 1 -> C2; 2 -> C3; 3 -> C4.
    """
    r = repartir(h_entreno=40.0, h_peri=0.0, momento_entreno=momento)
    comidas = r["comidas"]
    post = max(comidas, key=lambda k: comidas[k]["H"])
    assert post == f"C{momento + 1}", f"los hidratos no siguen al entreno: {comidas}"


def test_18_recolocar_el_entreno_no_cambia_el_total_del_dia():
    """Recolocar no es re-repartir el presupuesto: el dia suma lo mismo con cualquier momento."""
    referencia = totales(repartir(momento_entreno=0))
    for m in (1, 2, 3):
        for a, b in zip(totales(repartir(momento_entreno=m)), referencia):
            assert a == pytest.approx(b, abs=0.4)
    # Y el reparto, en cambio, tiene que ser distinto.
    assert repartir(momento_entreno=0)["comidas"] != repartir(momento_entreno=2)["comidas"]


# =====================================================================================
# CASO 19: los acordeones
# =====================================================================================

@pytest.mark.skip(reason="visual: que un acordeon salga plegado al ENTRAR DOS VECES depende del "
                         "estado inicial de React y del ancho de la ventana (en el telefono todas "
                         "cerradas, en escritorio la C1 abierta). Se comprueba en el navegador con "
                         "la extension, como manda la orden del 08-08")
def test_19_los_acordeones_abren_cerrados():
    """Caso 19: al abrir Nutricion dos veces, la Comida 1 no se despliega sola."""


# =====================================================================================
# CASO 20: los macros de una fecha pasada
# =====================================================================================

class FakeDB:
    """Lo justo para `macros_por_fecha`: el historial de ajustes del cliente."""

    def __init__(self, apuntes):
        self.macro_history = self._Col(apuntes)

    class _Col:
        def __init__(self, docs):
            self._docs = docs

        def find(self, *a, **kw):
            return self._Cursor(self._docs)

        class _Cursor:
            def __init__(self, docs):
                self._docs = docs

            async def to_list(self, _n=None):
                return list(self._docs)


IMPORTADO = "2026-08-05T01:10:39.707312+00:00"   # todos los apuntes de Calma entraron ese dia


def _ajuste(effective_date, hidratos):
    """Un ajuste del historial. `created_at` empata a proposito: es lo que pasa en produccion."""
    return {"client_id": "c1", "effective_date": effective_date, "created_at": IMPORTADO,
            "new_training": {"proteinas": 190, "hidratos": hidratos, "grasas": 60},
            "new_rest": {"proteinas": 225, "hidratos": hidratos, "grasas": 60},
            "peri": {"proteinas": 45, "hidratos": 50}}


HISTORIAL = [_ajuste("2026-01-10", 220), _ajuste("2026-05-02", 195), _ajuste("2026-08-01", 170)]
PERFIL = {"id": "c1",
          "macros_training": {"proteinas": 190, "hidratos": 170, "grasas": 60},
          "macros_rest": {"proteinas": 225, "hidratos": 170, "grasas": 60},
          "macros_periworkout": {"proteinas": 45, "hidratos": 50}}


def test_20_una_fecha_pasada_manda_con_los_macros_de_entonces():
    """Caso 20 [CRITICO]: un dia de marzo va con los macros vigentes en marzo."""
    entreno, _rest, _peri = correr(resolver(FakeDB(HISTORIAL), PERFIL, "2026-03-15"))
    assert entreno["hidratos"] == 220, "un dia de marzo no puede ir con los macros de agosto"


def test_20_y_hoy_con_los_de_hoy():
    entreno, _rest, _peri = correr(resolver(FakeDB(HISTORIAL), PERFIL, "2026-08-12"))
    assert entreno["hidratos"] == 170


def test_20_el_dia_del_ajuste_ya_manda_el_ajuste_nuevo():
    """`effective_date` es el dia en que entra en vigor, no el siguiente."""
    entreno, _r, _p = correr(resolver(FakeDB(HISTORIAL), PERFIL, "2026-05-02"))
    assert entreno["hidratos"] == 195


def test_20_antes_del_primer_ajuste_valen_los_mas_antiguos_que_haya():
    """Ya entrenaba con esos macros antes de que se empezara a registrar el historial."""
    entreno, _r, _p = correr(resolver(FakeDB(HISTORIAL), PERFIL, "2020-01-01"))
    assert entreno["hidratos"] == 220


def test_20_un_ajuste_con_fecha_por_delante_todavia_no_manda():
    """Hay ajustes programados; el de dentro de tres semanas no se le ha hecho aun."""
    historial = HISTORIAL + [_ajuste("2029-01-08", 120)]
    entreno, _r, _p = correr(resolver(FakeDB(historial), PERFIL, "2026-08-12"))
    assert entreno["hidratos"] == 170


def test_20_sin_historial_valen_los_del_perfil():
    entreno, _r, _p = correr(resolver(FakeDB([]), PERFIL, "2026-08-12"))
    assert entreno == PERFIL["macros_training"]
    assert correr(elegir_entrada(FakeDB(HISTORIAL), PERFIL, None)) is None


# =====================================================================================
# CONTRA EL BACKEND VIVO: los numeros que la pantalla pinta arriba salen de /distribute
# =====================================================================================

FECHA_PRUEBA = "2019-01-05"   # fecha de usar y tirar, para no pisar ningun dia del cliente demo


def _distribuir(cabeceras, **cambios):
    cuerpo = dict(tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
                  opcion_peri="intra_post")
    cuerpo.update(cambios)
    r = requests.post(f"{API}/calculator/distribute", headers=cabeceras, json=cuerpo, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    return r.json()


def test_11_el_objetivo_del_dia_sale_del_backend_y_cuadra(api_disponible, cabeceras_cliente):
    """Caso 11: los tres numeros del titular son los del reparto, y el reparto cuadra."""
    d = _distribuir(cabeceras_cliente)
    resumen = d["resumen"]
    for clave in ("P_total", "H_total", "G_total"):
        assert resumen[clave] > 0, f"{clave} a cero deja la pantalla pidiendo 0 de todo"

    peri = d["periworkout"]
    for macro_, total in (("P", "P_total"), ("H", "H_total")):
        suma_ = sum(c[macro_] for c in d["comidas"].values()) + sum(p[macro_] for p in peri.values())
        assert suma_ == pytest.approx(resumen[total], abs=0.4), \
            f"las comidas + el peri no suman el total del dia en {macro_}"


def test_12_lo_comido_se_guarda_y_se_recupera(api_disponible, cabeceras_cliente):
    """Caso 12 [CRITICO]: lo que la cabecera resta son los `macros_efectivos` del dia guardado.

    Se comprueba el viaje entero: se monta una comida, se guarda, se vuelve a Nutricion
    (GET del dia) y lo comido tiene que volver igual. Si volviera cambiado, el "te queda
    por comer" restaria otra cosa.
    """
    ya_existe = requests.get(f"{API}/diets/{FECHA_PRUEBA}", headers=cabeceras_cliente, timeout=20).json()
    if ya_existe.get("exists"):
        pytest.skip(f"el cliente demo ya tiene un dia guardado en {FECHA_PRUEBA}: no se pisa")

    comida = {"C1": {"alimentos": [{
        "alimento_id": 498, "nombre": "Pechuga de pollo", "cantidad_g": 200,
        "macros_efectivos": {"P": 40.0, "H": 0.0, "G": 0.0},
    }]}}
    try:
        guardado = requests.post(f"{API}/diets", headers=cabeceras_cliente, timeout=20, json={
            "fecha": FECHA_PRUEBA, "tipo_dia": "entrenamiento", "num_comidas": 4,
            "momento_entreno": 1, "opcion_peri": "intra_post", "comidas": comida,
            "is_cuadrado": False})
        assert guardado.status_code == 200, guardado.text

        vuelta = requests.get(f"{API}/diets/{FECHA_PRUEBA}", headers=cabeceras_cliente, timeout=20).json()
        assert vuelta.get("exists") is True
        alimentos = vuelta["comidas"]["C1"]["alimentos"]
        assert len(alimentos) == 1
        assert alimentos[0]["macros_efectivos"]["P"] == pytest.approx(40.0, abs=0.1)
        assert alimentos[0]["cantidad_g"] == pytest.approx(200, abs=0.1), \
            "la cantidad volvio cambiada: lo comido dejaria de cuadrar con lo que se puso"
    finally:
        requests.delete(f"{API}/diets/{FECHA_PRUEBA}", headers=cabeceras_cliente, timeout=20)


def test_20_el_backend_reparte_con_los_macros_vigentes_de_esa_fecha(api_disponible, cabeceras_cliente):
    """Caso 20 [CRITICO], contra el backend vivo y con el historial REAL del cliente demo.

    No hay numeros escritos a mano: se lee su historial de ajustes, se calcula cual estaba
    vigente en cada fecha y se comprueba que /distribute reparte con ese.
    """
    r = requests.get(f"{API}/macros/historial", headers=cabeceras_cliente, timeout=20)
    assert r.status_code == 200, r.text
    entradas = [e for e in (r.json().get("entradas") or []) if e.get("fecha") and e.get("entreno")]
    if len(entradas) < 2:
        pytest.skip("el cliente demo no tiene historial suficiente para comparar dos fechas")

    # De la mas nueva a la mas vieja. `sort` es estable, asi que dos ajustes del mismo dia
    # conservan el orden en que los da el backend (el ultimo guardado primero), que es el
    # mismo desempate que usa `macros_por_fecha.elegir_entrada`.
    entradas.sort(key=lambda e: e["fecha"], reverse=True)

    def vigente_en(fecha):
        aplicables = [e for e in entradas if e["fecha"] <= fecha]
        return aplicables[0] if aplicables else entradas[-1]

    # Dos fechas de su historial cuyos macros vigentes NO coincidan: si no las hay, el caso
    # no se puede distinguir con estos datos y no vale enganarse dandolo por bueno.
    fechas = sorted({e["fecha"] for e in entradas}, reverse=True)
    pareja = next(((a, b) for i, a in enumerate(fechas) for b in fechas[i + 1:]
                   if vigente_en(a)["entreno"] != vigente_en(b)["entreno"]), None)
    if not pareja:
        pytest.skip("todos sus ajustes tienen los mismos macros de entreno: no distinguen fecha")

    for fecha in pareja:
        esperado = vigente_en(fecha)["entreno"]
        resumen = _distribuir(cabeceras_cliente, fecha=fecha)["resumen"]
        assert resumen["P_entreno"] == pytest.approx(esperado["proteina"], abs=0.1), fecha
        assert resumen["H_entreno"] == pytest.approx(esperado["hidratos"], abs=0.1), fecha
        assert resumen["G_entreno"] == pytest.approx(esperado["grasa"], abs=0.1), fecha
