# -*- coding: utf-8 -*-
"""Extras del día (apartado 5 del doc del 21-08; puntos 27 a 33 del doc del 24-08).

Lo que el cliente se come fuera de su dieta se apunta en `extras`, una lista hermana de
`comidas` en el documento del día. Desde el 24-08 la puerta buena es TEXTO LIBRE
(`POST /diets/{fecha}/extras` con `{"texto": ...}`, sin catálogo y sin macros), la vieja
del catálogo sigue abierta porque hay extras así guardados, y los extras NO cuentan en
nada: `servido_comidas` no debe moverse por un extra. `GET /diets/extras/periodo` los saca
todos de una quincena, que es donde le sirven al equipo.
"""
import requests

from conftest import API, CLIENT_EMAIL, CLIENT_PASSWORD

FECHA = "2030-02-12"  # una fecha lejana que no pisa datos de nadie


def _token():
    r = requests.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _limpiar(cab, fecha=FECHA):
    requests.delete(f"{API}/diets/{fecha}", headers=cab, timeout=30)


def _un_alimento(cab):
    """Un alimento real del catálogo con macros que contar."""
    r = requests.get(f"{API}/calculator/foods", params={"limit": 50}, headers=cab, timeout=30)
    assert r.status_code == 200, r.text
    for f in r.json():
        if (f.get("proteinas") or f.get("hidratos") or f.get("grasas")):
            return f
    raise AssertionError("No hay alimentos con macros en el catálogo local")


def test_apuntar_un_extra_escribiendolo_sin_catalogo():
    """La puerta del punto 27: un campo de texto y ya. Sin alimento y SIN MACROS."""
    cab = _token()
    _limpiar(cab)
    try:
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"texto": "  Dos cañas y un   pincho de tortilla  ",
                                "origen": "inicio"},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        extra = r.json()["extra"]
        # Los espacios de más se limpian: es lo que se va a pintar en la lista.
        assert extra["texto"] == "Dos cañas y un pincho de tortilla"
        assert extra["nombre"] == extra["texto"]  # quien lee `nombre` sigue funcionando
        assert extra["alimento_id"] is None
        assert extra["macros"] is None
        assert extra["origen"] == "inicio"
        assert extra["id"]

        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        guardados = dia.get("extras") or []
        assert [e["texto"] for e in guardados] == ["Dos cañas y un pincho de tortilla"]

        r = requests.delete(f"{API}/diets/{FECHA}/extras/{extra['id']}", headers=cab, timeout=30)
        assert r.status_code == 200, r.text
    finally:
        _limpiar(cab)


def test_texto_en_blanco_y_texto_kilometrico():
    """Los dos noes del campo de texto, con frase humana."""
    cab = _token()
    _limpiar(cab)
    try:
        for vacio in ("", "   ", None):
            r = requests.post(f"{API}/diets/{FECHA}/extras", json={"texto": vacio},
                              headers=cab, timeout=30)
            assert r.status_code == 400, f"{vacio!r} tendría que rechazarse: {r.status_code}"
            assert "Escribe" in r.json()["detail"]

        r = requests.post(f"{API}/diets/{FECHA}/extras", json={"texto": "tarta " * 100},
                          headers=cab, timeout=30)
        assert r.status_code == 400, r.text

        # Un cuerpo sin nada tampoco es un 404 de catálogo: es «escribe qué te has comido».
        r = requests.post(f"{API}/diets/{FECHA}/extras", json={}, headers=cab, timeout=30)
        assert r.status_code == 400, r.text

        # Y un origen inventado no se guarda, pero tampoco tumba el extra.
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"texto": "un helado", "origen": "loquesea"},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["extra"]["origen"] is None
    finally:
        _limpiar(cab)


def test_los_tres_origenes_del_mismo_campo():
    """El bloque se monta en Inicio y en Nutrición, y el check-in escribe en la misma
    lista: los tres orígenes se guardan tal cual para saber por dónde lo apunta la gente."""
    cab = _token()
    _limpiar(cab)
    try:
        for origen in ("inicio", "nutricion", "checkin"):
            r = requests.post(f"{API}/diets/{FECHA}/extras",
                              json={"texto": f"algo de {origen}", "origen": origen},
                              headers=cab, timeout=30)
            assert r.status_code == 200, r.text
            assert r.json()["extra"]["origen"] == origen
        # Y quien no lo diga se queda sin origen, no con uno inventado: un origen falseado
        # no se nota nunca; uno vacío se ve y se arregla.
        r = requests.post(f"{API}/diets/{FECHA}/extras", json={"texto": "algo sin decir de donde"},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["extra"]["origen"] is None

        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert [e["origen"] for e in dia["extras"]] == ["inicio", "nutricion", "checkin", None]
    finally:
        _limpiar(cab)


def test_un_extra_no_configura_el_dia():
    """El extra hace upsert del día, pero ese documento NO lleva configuración dentro.

    De esto depende el Inicio: si un día que existe solo porque se apuntó el café de las
    10:00 contara como «día configurado», a quien tiene 3 comidas le pintaría 4 vacías.
    El marcador es `num_comidas`, que solo lo escribe un guardado de dieta de verdad.
    """
    cab = _token()
    _limpiar(cab)
    try:
        r = requests.post(f"{API}/diets/{FECHA}/extras", json={"texto": "un café con leche"},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert dia["exists"] is True
        assert dia.get("num_comidas") is None, "el extra no puede configurar el día"
        assert not dia.get("comidas")
        assert dia["servido_comidas"] == {"P": 0.0, "H": 0.0, "G": 0.0}
    finally:
        _limpiar(cab)


def test_la_puerta_vieja_del_catalogo_sigue_abierta():
    """Hay extras del catálogo guardados en producción: el contrato viejo no se rompe."""
    cab = _token()
    _limpiar(cab)
    try:
        food = _un_alimento(cab)
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"alimento_id": food["id"], "cantidad_g": 100},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        extra = r.json()["extra"]
        assert extra["id"] and extra["alimento_id"] == food["id"]
        assert extra["nombre"] == food["nombre"]
        assert extra["cantidad_g"] == 100
        macros = extra["macros"]
        # Macros de etiqueta calculados al añadir: alguno tiene que contar.
        assert (macros["P"] + macros["H"] + macros["G"]) > 0

        # Persiste: /diets/{fecha} devuelve el día (upsertado) con su extra.
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        guardados = dia.get("extras") or []
        assert [e["id"] for e in guardados] == [extra["id"]]
        assert guardados[0]["macros"] == macros

        # Y borrar borra: la lista queda vacía y repetir el borrado es un 404.
        r = requests.delete(f"{API}/diets/{FECHA}/extras/{extra['id']}", headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert not (dia.get("extras") or [])
        r = requests.delete(f"{API}/diets/{FECHA}/extras/{extra['id']}", headers=cab, timeout=30)
        assert r.status_code == 404, r.text
    finally:
        _limpiar(cab)


def test_el_servido_de_comidas_no_cuenta_los_extras():
    """Un extra NO toca la dieta (punto 28): `servido_comidas` sale de las comidas y no
    debe moverse ni un gramo, ni con un extra del catálogo ni con uno escrito."""
    cab = _token()
    _limpiar(cab)
    try:
        food = _un_alimento(cab)
        # Un día con UNA comida montada de verdad...
        r = requests.post(f"{API}/diets", headers=cab, timeout=30, json={
            "fecha": FECHA, "tipo_dia": "entrenamiento", "num_comidas": 4,
            "comidas": {"C1": {"alimentos": [
                {"alimento_id": food["id"], "nombre": food["nombre"], "cantidad_g": 100},
            ]}},
        })
        assert r.status_code == 200, r.text
        antes = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()["servido_comidas"]

        # ...y dos extras encima: el servido de las comidas tiene que quedarse igual.
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"alimento_id": food["id"], "cantidad_g": 250},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"texto": "media tarta de cumpleaños"}, headers=cab, timeout=30)
        assert r.status_code == 200, r.text

        dia = requests.get(f"{API}/diets/{FECHA}", headers=cab, timeout=30).json()
        assert dia["servido_comidas"] == antes
        assert len(dia.get("extras") or []) == 2
        # Y las comidas siguen intactas: el extra es hermano, no entra en `comidas`.
        assert len(dia["comidas"]["C1"]["alimentos"]) == 1
    finally:
        _limpiar(cab)


def test_alimento_inexistente_y_cantidades_basura():
    cab = _token()
    r = requests.post(f"{API}/diets/{FECHA}/extras",
                      json={"alimento_id": -999999, "cantidad_g": 100}, headers=cab, timeout=30)
    assert r.status_code == 404, r.text

    food = _un_alimento(cab)
    for cantidad in (0, -50, "nada", None, 999999):
        r = requests.post(f"{API}/diets/{FECHA}/extras",
                          json={"alimento_id": food["id"], "cantidad_g": cantidad},
                          headers=cab, timeout=30)
        assert r.status_code == 400, f"cantidad {cantidad!r} tendría que rechazarse: {r.status_code}"

    r = requests.post(f"{API}/diets/una-fecha-mala/extras",
                      json={"texto": "un helado"}, headers=cab, timeout=30)
    assert r.status_code == 400, r.text


def test_la_fecha_es_la_que_le_pasan_no_la_de_hoy():
    """El check-in de la noche (punto 32) escribe en la MISMA lista y con SU día: si el
    endpoint forzara «hoy», el extra de las 23:50 aparecería mañana."""
    cab = _token()
    ayer, hoy = "2030-02-10", "2030-02-11"
    _limpiar(cab, ayer)
    _limpiar(cab, hoy)
    try:
        r = requests.post(f"{API}/diets/{ayer}/extras",
                          json={"texto": "cervezas de la cena", "origen": "checkin"},
                          headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["fecha"] == ayer
        assert r.json()["extra"]["origen"] == "checkin"

        del_dia_de_ayer = requests.get(f"{API}/diets/{ayer}", headers=cab, timeout=30).json()
        assert [e["texto"] for e in (del_dia_de_ayer.get("extras") or [])] == ["cervezas de la cena"]
        # Y el día siguiente ni se entera.
        del_dia_de_hoy = requests.get(f"{API}/diets/{hoy}", headers=cab, timeout=30).json()
        assert not (del_dia_de_hoy.get("extras") or [])
    finally:
        _limpiar(cab, ayer)
        _limpiar(cab, hoy)


def test_los_extras_del_periodo_salen_juntos_y_en_orden():
    """Punto 33: todos los de la quincena en una lista, que es donde sirven."""
    cab = _token()
    dias = ["2030-02-10", "2030-02-11", "2030-02-14"]
    for d in dias:
        _limpiar(cab, d)
    try:
        requests.post(f"{API}/diets/{dias[0]}/extras", json={"texto": "dos cañas"},
                      headers=cab, timeout=30)
        requests.post(f"{API}/diets/{dias[1]}/extras", json={"texto": "un pincho de tortilla"},
                      headers=cab, timeout=30)
        requests.post(f"{API}/diets/{dias[1]}/extras", json={"texto": "helado"},
                      headers=cab, timeout=30)
        # Este cae fuera de la quincena que se pide.
        requests.post(f"{API}/diets/{dias[2]}/extras", json={"texto": "tarta"},
                      headers=cab, timeout=30)

        r = requests.get(f"{API}/diets/extras/periodo",
                         params={"desde": "2030-02-10", "hasta": "2030-02-13"},
                         headers=cab, timeout=30)
        assert r.status_code == 200, r.text
        datos = r.json()
        assert datos["total"] == 3
        assert [e["texto"] for e in datos["extras"]] == ["dos cañas", "un pincho de tortilla", "helado"]
        assert [e["fecha"] for e in datos["extras"]] == [dias[0], dias[1], dias[1]]

        # Fechas al revés y fecha basura: se dicen, no revientan.
        r = requests.get(f"{API}/diets/extras/periodo",
                         params={"desde": "2030-02-13", "hasta": "2030-02-10"},
                         headers=cab, timeout=30)
        assert r.status_code == 400, r.text
        r = requests.get(f"{API}/diets/extras/periodo",
                         params={"desde": "hola", "hasta": "2030-02-10"},
                         headers=cab, timeout=30)
        assert r.status_code == 400, r.text

        # Y un periodo de años no se sirve a medias: se dice que no. Una lista recortada
        # en silencio saldría en el reporte como si esos extras no hubieran existido.
        r = requests.get(f"{API}/diets/extras/periodo",
                         params={"desde": "2020-01-01", "hasta": "2030-02-13"},
                         headers=cab, timeout=30)
        assert r.status_code == 400, r.text
        # Un año justo sí entra: el quincenal y el mensual caben de sobra.
        r = requests.get(f"{API}/diets/extras/periodo",
                         params={"desde": "2030-02-10", "hasta": "2031-02-09"},
                         headers=cab, timeout=30)
        assert r.status_code == 200, r.text
    finally:
        for d in dias:
            _limpiar(cab, d)


def test_un_cliente_no_ve_los_extras_de_otro():
    """El `user_id` del periodo es solo para el equipo: la ficha de otro no se abre."""
    cab = _token()
    r = requests.get(f"{API}/diets/extras/periodo",
                     params={"desde": "2030-02-10", "hasta": "2030-02-13",
                             "user_id": "otro-cliente-cualquiera"},
                     headers=cab, timeout=30)
    assert r.status_code == 403, r.text


def test_sin_sesion_no_hay_extras():
    r = requests.post(f"{API}/diets/{FECHA}/extras",
                      json={"texto": "un helado"}, timeout=30)
    assert r.status_code in (401, 403)
    r = requests.delete(f"{API}/diets/{FECHA}/extras/loquesea", timeout=30)
    assert r.status_code in (401, 403)
    r = requests.get(f"{API}/diets/extras/periodo",
                     params={"desde": "2030-02-10", "hasta": "2030-02-13"}, timeout=30)
    assert r.status_code in (401, 403)
