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

# El bloque que decide el titular y el numero grande, tal cual esta en el fichero, metido
# en un envoltorio minimo. Lo unico que pone este harness es la entrada (`macros`) y la
# salida (JSON); las cuatro decisiones -- nada puesto, pasado, cuadrado, titular -- y la
# cuenta del numero grande son las lineas del componente, copiadas en tiempo de ejecucion.
_PLANTILLA_JS = r"""
const casos = %(casos)s;
const salida = casos.map((macros) => {
%(bloque)s
  const numeros = {};
  for (const m of macros) {
    const val = m.val, tgt = m.tgt;
%(over)s
%(grande)s
    numeros[m.key] = grande;
  }
  return { titular, nadaPuesto, pasado, cuadrado, numeros };
});
// A ASCII: el titular lleva tilde ("Dia cuadrado") y la consola de Windows no siempre la
// deja pasar entera. Con las escapadas \uXXXX el JSON viaja igual en cualquier consola.
console.log(JSON.stringify(salida).replace(/./gu, (c) => {
  const n = c.codePointAt(0);
  return n > 126 ? "\\u" + n.toString(16).padStart(4, "0") : c;
}));
"""


def _trozo(texto, desde, hasta, que):
    assert desde in texto, f"no encuentro {que} en DayHeader.jsx (buscaba {desde!r})"
    i = texto.index(desde)
    j = texto.index(hasta, i)
    return texto[i:j]


def _logica_del_titular():
    """Las lineas vivas de DayHeader.jsx: el bloque del titular, `over` y `grande`."""
    texto = DAY_HEADER.read_text(encoding="utf-8")
    bloque = _trozo(texto, "const nadaPuesto", "return (", "el bloque del titular")
    desde_el_bloque = texto[texto.index("const nadaPuesto"):]
    over = re.search(r"const over = .*?;", desde_el_bloque)
    grande = re.search(r"const grande = .*?;", desde_el_bloque)
    assert over and grande, "no encuentro `over`/`grande` en DayHeader.jsx: mira si cambio la cabecera"
    return bloque, over.group(0), grande.group(0)


@pytest.fixture(scope="module")
def titular_de():
    """Devuelve una funcion que evalua el titular del dia para unos macros dados."""
    if not shutil.which("node"):
        pytest.skip("hace falta node para ejecutar la logica del titular tal cual esta en DayHeader.jsx")
    bloque, over, grande = _logica_del_titular()

    def _evaluar(*casos):
        js = _PLANTILLA_JS % {
            "casos": json.dumps(list(casos)),
            "bloque": bloque,
            "over": "    " + over,
            "grande": "    " + grande,
        }
        with tempfile.TemporaryDirectory() as tmp:
            fichero = pathlib.Path(tmp) / "titular.mjs"
            fichero.write_text(js, encoding="utf-8")
            salida = subprocess.run(["node", str(fichero)], capture_output=True, text=True)
        assert salida.returncode == 0, f"node fallo: {salida.stderr}"
        return json.loads(salida.stdout)

    return _evaluar


def macro(key, val, tgt):
    return {"key": key, "val": val, "tgt": tgt}


# Objetivo de las comidas del cliente demo (dia de entreno, sin contar el perientreno,
# que la cabecera lleva por su cuenta): 190 P, 135 H, 60 G.
OBJETIVO = [macro("P", 0, 190), macro("H", 0, 135), macro("G", 0, 60)]


def _con_comido(p, h, g):
    return [macro("P", p, 190), macro("H", h, 135), macro("G", g, 60)]


def test_11_el_dia_a_cero_dice_lo_que_hay_que_comer(titular_de):
    """Caso 11: con el dia a cero, "hoy tienes que comer" y los tres numeros del objetivo."""
    r = titular_de(OBJETIVO)[0]
    assert r["titular"] == "Hoy tienes que comer"
    assert r["numeros"] == {"P": 190, "H": 135, "G": 60}, "a cero, el numero grande ES el objetivo"


def test_12_con_una_comida_montada_resta_lo_comido(titular_de):
    """Caso 12 [CRITICO]: el titular pasa a "te queda por comer" y el numero es lo que falta."""
    r = titular_de(_con_comido(47, 51, 12))[0]
    assert r["titular"] == "Te queda por comer"
    assert r["numeros"] == {"P": 143, "H": 84, "G": 48}, "tiene que restar lo comido, no sumarlo"


def test_13_pasarse_de_un_macro_lo_dice(titular_de):
    """Caso 13 [CRITICO]: pasarse dice "te has pasado"."""
    r = titular_de(_con_comido(200, 175, 62))[0]
    assert r["titular"] == "Te has pasado"


def test_13_nunca_sale_un_numero_negativo(titular_de):
    """Caso 13 [CRITICO]: nunca un "faltan -8 H".

    Los dos caminos por los que salia: pasarse de largo (y ahi se ensena lo comido) y
    pasarse de poco -- por debajo del margen de 4 g --, que es el que daba el negativo,
    porque el macro no cuenta como "pasado" y se seguia restando objetivo menos comido.
    """
    casos = [
        _con_comido(200, 175, 62),     # pasado de largo
        _con_comido(193, 138, 63),     # pasado de poco: 3 g por encima en los tres
        _con_comido(190, 143, 60),     # solo un macro, y por poco
        _con_comido(400, 400, 400),    # el doble de todo
    ]
    for entrada, r in zip(casos, titular_de(*casos)):
        for clave, valor in r["numeros"].items():
            assert valor >= 0, f"numero negativo en {clave} con {entrada}: {r}"


def test_13_dice_por_cuanto_se_ha_pasado(titular_de):
    """Caso 13, la otra mitad: "dice 'te has pasado' Y POR CUANTO". FALLA A PROPOSITO.

    Hoy la cabecera no lo dice: cuando te pasas, el numero grande es lo COMIDO (200) y
    debajo, en pequeno, "de 190". Los dos numeros estan, pero el exceso -- 10 g -- no
    aparece en ninguna parte: lo tiene que restar el cliente de cabeza, que es justo lo
    que el rediseno queria quitar del "120 / 190".

    Se deja en rojo porque es lo que Jesus pide y no esta hecho, no porque el codigo este
    roto. Para cerrarlo hay que decidir con el si el numero grande pasa a ser el exceso
    ("te has pasado 10 g de proteina") o si se anade una linea debajo.
    """
    r = titular_de(_con_comido(200, 175, 62))[0]
    assert r["numeros"]["P"] == 10, \
        "no se dice por cuanto te has pasado: el numero grande es lo comido, no el exceso"


def test_14_el_dia_cuadrado_lo_dice(titular_de):
    """Caso 14: cuadrar el dia entero dice "dia cuadrado"."""
    r = titular_de(_con_comido(190, 135, 60))[0]
    assert r["titular"].replace("í", "i") == "Dia cuadrado"
    assert r["cuadrado"] is True


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

    El aviso vive en DayHeader: mientras el dia esta sin marcar, el conmutador sale con el
    aro naranja (`diaSinMarcar`) y en escritorio ademas con la frase. La app abre en
    "Entreno" porque tiene que abrir en algo, y en un dia de descanso eso son 60 g de
    hidratos de mas: por eso el aviso se da ANTES de elegir, no despues.
    """
    texto = DAY_HEADER.read_text(encoding="utf-8")
    assert "Tus macros cambian" in texto, "se ha perdido la frase que avisa del cambio"
    assert "diaSinMarcar ? 'ring-2 ring-brand" in texto, \
        "se ha perdido el aro del conmutador, que es el aviso en el telefono"


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
