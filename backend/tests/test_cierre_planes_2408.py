"""
Cierre del 24-08, bloque «planes, accesos y el alta».

Sin base de datos y sin servidor: todo lo de aqui son reglas de catalogo, que es donde
estaban los tres fallos. Cada prueba empieza contando a quien le pasaba.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.plan_access import (                                    # noqa: E402
    dias_hasta_la_revision,
    modo_calculadora,
    plan_grants_feature,
)
from models.user import (                                         # noqa: E402
    ALIAS_EXTRA,
    PLAN_CATALOG,
    PLAN_TYPES,
    codigo_de_plan,
    derive_features,
    merged_catalog,
    nivel_suplementacion,
    opciones_de_renovacion,
    plan_habilitaciones,
)


# ── El chat es del que tiene entrenador detras ────────────────────────────────────────
#
# Al equipo, cada lunes: en la lista «sin contactar» del panel le salian los clientes de El
# Lunes Empiezo, Calculadora, Mantenimiento, Calculadora JP y Basica -- unos 83 de los 200
# perfiles --, que por decision de producto no tienen chat. `derive_features` metia «chat»
# para todos sin mirar nada, asi que los tres filtros que se apoyan en el (routes/paneles.py
# y las dos listas de routes/admin.py) no dejaban fuera a nadie y el entrenador perseguia a
# gente a la que no puede escribir por ahi.

SIN_ACOMPANAMIENTO = ("nivel1", "elm", "mantenimiento", "calculadora_jp", "basica")
CON_ACOMPANAMIENTO = ("nivel2", "nivel3", "gold", "silver", "bronze", "calma12",
                      "reto12en12_gold", "personalizado", "plan_6m")


def test_el_plan_sin_entrenador_no_lleva_chat():
    for code in SIN_ACOMPANAMIENTO:
        assert "chat" not in PLAN_TYPES[code]["features"], (
            f"{code} vuelve a salir en la lista de «sin contactar» del panel")
        assert plan_grants_feature(code, "chat") is False


def test_el_plan_con_entrenador_si_lleva_chat():
    for code in CON_ACOMPANAMIENTO:
        assert "chat" in PLAN_TYPES[code]["features"], (
            f"a {code} se le ha quitado el chat y ese SI tiene a alguien detras")


def test_el_premium_no_se_queda_fuera_por_llevar_llamadas():
    """El Gold es `con_entrenador` y el Premium `con_entrenador_y_llamadas`: si el criterio
    fuera la igualdad y no el prefijo, el plan que MAS acompanamiento tiene y el mas caro se
    quedaria sin chat. Mismo criterio que CAP.CHAT en frontend/src/lib/planAccess.js."""
    assert plan_habilitaciones("nivel3")["acompanamiento"] == "con_entrenador_y_llamadas"
    assert "chat" in PLAN_TYPES["nivel3"]["features"]


def test_el_legacy_que_no_declara_acompanamiento_conserva_su_chat():
    """Los planes antiguos del catalogo (Gold, Silver, CALMA 12...) no traen el campo, que se
    añadio el 31-07: sin la misma deduccion que hace `completar_acompanamiento` -- con
    reportes hay alguien mirando -- se habrian quedado sin chat de golpe, que es justo lo
    contrario de lo que se buscaba."""
    assert "chat" in derive_features({"reportes": ["mensual"], "calculadora": "personalizado"})
    assert "chat" not in derive_features({"reportes": [], "calculadora": "autogestion"})


def test_los_macros_siguen_siendo_de_todos():
    """El otro valor que arrancaba fijo en la lista. Ese si es de todos: la calculadora la
    tiene hasta el que solo paga el Mantenimiento."""
    for code in PLAN_CATALOG:
        assert "macros" in PLAN_TYPES[code]["features"]


# ── Al 6M hay que decirle por que su plan no esta en la lista ─────────────────────────
#
# Son 2 perfiles en la base. Su plan esta en estado «especial»: no es legacy -- no se
# retiro de nada -- y tampoco «activo», asi que no le salia «Seguir igual» y tampoco la
# frase que lo explica, porque el motivo solo se escribia para los retirados. Veia la lista
# de los otros planes y ni una linea que le dijera por que el suyo no estaba.

def test_el_plan_especial_trae_su_frase():
    r = opciones_de_renovacion("plan_6m")
    assert PLAN_CATALOG["plan_6m"]["estado"] == "especial"
    assert r["puede_seguir_igual"] is False, "el 6M se renueva hablando, no por la pasarela"
    assert r["motivo"], "se queda sin una sola linea que le explique por que"
    assert not r["motivo"].endswith("."), (
        "RenovacionPage pinta «{motivo_cambio}.», asi que el punto lo pone la pantalla")


def test_al_legacy_retirado_no_se_le_cambia_el_motivo():
    """El que si estaba resuelto sigue igual: «tu plan ya no se ofrece»."""
    cat = merged_catalog({"calculadora_jp": {"renovable_por_los_suyos": False}})
    assert "ya no se ofrece" in opciones_de_renovacion("calculadora_jp", cat)["motivo"]


def test_al_plan_que_se_vende_no_se_le_explica_nada():
    for code in ("nivel1", "nivel2", "nivel3", "elm", "mantenimiento"):
        assert opciones_de_renovacion(code)["motivo"] is None, (
            f"a {code}, que se sigue vendiendo, se le esta dando una excusa")


def test_la_frase_del_plan_a_medida_no_se_la_come_un_complemento():
    """Escrita como «todo lo que no sea activo ni legacy» se llevaba tambien los cuatro
    `complemento` -- la rutina del mes, la personalizada, la revision de macros y las
    formaciones --, y a esos se les decia «tu plan es a medida: su renovacion la vemos
    contigo» cuando no son un plan: son extras que se compran sueltos."""
    complementos = [c for c, p in PLAN_CATALOG.items() if p.get("estado") == "complemento"]
    assert complementos, "si desaparecen los complementos, esta prueba ya no vigila nada"
    for code in complementos:
        assert opciones_de_renovacion(code)["motivo"] is None, (
            f"a {code}, que es un complemento, se le esta contando que su plan es a medida")


# ── Lo que el admin edita del plan tiene que llegar al cerrojo ────────────────────────
#
# El admin cambiaba la Calculadora de un plan en el panel: la tarjeta y el menu del cliente
# cambiaban al momento (esos leen GET /plans, que si aplica los overrides) y el cerrojo del
# servidor seguia con el valor escrito en el codigo. `modo_calculadora` y
# `dias_hasta_la_revision` ya aceptan el catalogo mezclado, y sus versiones «_vivo» lo leen
# de la base como hace `plan_features_vivo`.

def test_la_calculadora_editada_en_el_panel_manda():
    cat = merged_catalog({"nivel1": {"habilitaciones": {"calculadora": "personalizado"}}})
    assert modo_calculadora("nivel1") == "autogestion", "el del codigo, sin overrides"
    assert modo_calculadora("nivel1", cat) == "personalizado", (
        "lo que el admin acaba de guardar no llega al candado del servidor")


def test_la_cadencia_editada_en_el_panel_manda():
    cat = merged_catalog({"nivel1": {"habilitaciones": {"reportes": ["quincenal", "mensual"]}}})
    assert dias_hasta_la_revision("nivel1") == 28
    assert dias_hasta_la_revision("nivel1", cat) == 14


def test_el_plan_escrito_como_lo_traen_los_migrados_encuentra_su_ficha():
    """Las dos buscaban con el plan en minusculas y nada mas, sin `codigo_de_plan`, asi que
    un perfil escrito «CalMa» o «premium 177 mensual» no casaba con ninguna ficha: modo
    "sin_ajuste" y revision cada 28 dias, los valores del plan desconocido.

    Se veia desde que la app resuelve alias (`planDelCatalogo`): al de «CalMa» la pantalla le
    decia «tus macros te los ajustamos nosotros» y el servidor se los aplicaba solo, sin
    esperar al coach. Antes los dos lados fallaban igual y al menos no se contradecian."""
    for grafia in ("CalMa", "Membresía", "premium 177 mensual", "lunes empiezo", "Plan 6 M"):
        code = codigo_de_plan(grafia)
        assert code in PLAN_CATALOG, f"{grafia} ya no resuelve a ningun plan"
        assert modo_calculadora(grafia) == modo_calculadora(code), (
            f"a {grafia} se le aplica un modo de calculadora distinto al de su plan")
        assert dias_hasta_la_revision(grafia) == dias_hasta_la_revision(code)
    # Y que no coincidan por casualidad con lo que da un plan que no existe.
    assert modo_calculadora("CalMa") == "personalizado"
    assert dias_hasta_la_revision("premium 177 mensual") == 7
    assert modo_calculadora("un plan que no existe") == "sin_ajuste"
    assert dias_hasta_la_revision("un plan que no existe") == 28


def test_las_grafias_sueltas_viajan_en_la_ficha_del_plan():
    """La app resuelve el plan del perfil con los alias que trae cada ficha en GET /plans, no
    con `ALIAS_DE_PLAN`. Las doce grafias de `ALIAS_EXTRA` no las declaraba ninguna, o sea que
    «premium 177 mensual» seguia dejando al cliente sin una sola habilitacion en la app."""
    for grafia, code in ALIAS_EXTRA.items():
        alias = [str(a).lower().strip() for a in (PLAN_CATALOG[code].get("alias") or [])]
        assert grafia in alias, f"«{grafia}» no viaja en la ficha de {code}"
    # Y por la puerta que las mira de verdad, la del servidor, siguen igual.
    assert codigo_de_plan("Premium 177 mensual") == "premium"


def test_el_respaldo_del_catalogo_vivo_es_un_catalogo_entero():
    """`catalogo_vivo` cae en `merged_catalog()` cuando la base no contesta, y no en
    `PLAN_CATALOG` a pelo: el crudo no trae `code`, no trae `features` y no pasa las
    habilitaciones por `completar_acompanamiento`, asi que el que leyera cualquiera de esos
    tres se encontraria un vacio sin un solo error justo el dia que Mongo falla."""
    respaldo = merged_catalog()
    for code, p in respaldo.items():
        assert p.get("code") == code
        assert p.get("features"), f"{code} se quedaria sin features"
        assert p["habilitaciones"].get("acompanamiento"), f"{code} se quedaria sin chat"
    assert "code" not in PLAN_CATALOG["nivel1"], (
        "si el crudo ya trae `code`, esta prueba dejo de decir por que se cambio el respaldo")


def test_sin_overrides_todo_se_queda_como_estaba():
    """El parametro es opcional a proposito: los sitios que todavia llaman en seco tienen
    que seguir dando exactamente lo mismo que antes."""
    for code in PLAN_CATALOG:
        cat = merged_catalog()
        assert modo_calculadora(code) == modo_calculadora(code, cat)
        assert dias_hasta_la_revision(code) == dias_hasta_la_revision(code, cat)


# ── Las dos filas de la comparativa de /planes ────────────────────────────────────────
#
# Al que se planteaba comprar el Nivel 1 por 247 € se le decia «Suplementacion:
# Personalizada» cuando lo que lleva es la guia generica, y «Rutina: no» cuando su propia
# ficha, dos lineas mas arriba, dice «calculadora, rutina del mes y reporte mensual». La
# pantalla es JSX y no se prueba desde aqui; lo que se fija es el dato que ahora respeta,
# con la funcion gemela de la del front (`nivelSuplementacion` en lib/planAccess.js).

def test_el_nivel1_lleva_la_guia_y_la_rutina_del_mes():
    h = plan_habilitaciones("nivel1")
    assert nivel_suplementacion(h) == "guia", "no es el protocolo del coach: es la guia"
    assert h["rutina"] == "del_mes", "la fila «Rutina» no puede decir que no lleva"


def test_el_gold_y_el_premium_si_llevan_protocolo():
    for code in ("nivel2", "nivel3"):
        assert nivel_suplementacion(plan_habilitaciones(code)) == "protocolo"
        assert plan_habilitaciones(code)["rutina"] == "personalizada"
