"""«El último ajuste» de un cliente se elige por su fecha de VIGENCIA, no por la de la fila.

Salió el 12-08-2026 tirando del hilo del «AJUSTES 176» de Jesús.

En las 3.446 filas de `macro_history` que vinieron de Calma, `created_at` es el día en que se
importaron -- todas el 05-08-2026, muchas en el mismo milisegundo -- y `effective_date` es el
día en que el ajuste entró en vigor. Media app pedía «el último» con
`find_one(sort=[("created_at", -1)])`, o sea a suertes entre toda la historia del cliente.

Medido contra producción: **a 140 de 185 clientes les salía mal**. Un ejemplo real: se cogía
el ajuste del 2022-12-10 (60 g de hidratos) en vez del del 2026-07-31 (80 g). Y el aviso de
«lleva más de 45 días sin que le ajusten» saltaba para 4 clientes; contado bien, para 79: la
fecha de importación tapaba a los otros 75.

Lo que NUNCA estuvo mal son los macros que come el cliente: eso ya salía de
`macros_por_fecha.resolver`, que siempre miró `effective_date`. Estaba mal quién se los puso,
cuándo se le ajustó por última vez y qué llama «tus macros nuevos» el informe mensual.

Corre sin Mongo: la colección se sustituye por una lista.
"""
import asyncio
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from macros_por_fecha import ultima_vigente  # noqa: E402

CLIENTE = "c-1"

# Un cliente migrado: toda su historia importada el mismo día, con su vigencia de verdad.
IMPORTADO = "2026-08-05T01:10:39.707312+00:00"
FILAS = [
    {"id": "a", "client_id": CLIENTE, "effective_date": "2022-12-10", "created_at": IMPORTADO,
     "training": {"carbs": 60}, "origen": "calma"},
    {"id": "b", "client_id": CLIENTE, "effective_date": "2026-07-31", "created_at": IMPORTADO,
     "training": {"carbs": 80}, "origen": "calma"},
    {"id": "c", "client_id": CLIENTE, "effective_date": "2029-01-08", "created_at": IMPORTADO,
     "training": {"carbs": 999}, "origen": "calma"},   # programado, aún no toca
]


class _Coleccion:
    def __init__(self, filas):
        self.filas = filas

    def find(self, filtro, _proj=None):
        seleccion = [f for f in self.filas if f["client_id"] == filtro.get("client_id")]
        return _Cursor(seleccion)


class _Cursor:
    def __init__(self, filas):
        self.filas = filas

    async def to_list(self, _n):
        return self.filas


class _Db:
    def __init__(self, filas):
        self.macro_history = _Coleccion(filas)


def elegido(filas, fecha="2026-08-12"):
    return asyncio.run(ultima_vigente(_Db(filas), CLIENTE, fecha))


def test_gana_la_vigencia_mas_reciente_no_la_fila_mas_nueva():
    """El caso real: se cogía el de 2022 teniendo uno de julio de 2026."""
    assert elegido(FILAS)["effective_date"] == "2026-07-31"


def test_un_ajuste_programado_todavia_no_se_ha_hecho():
    """La cuenta de Jesús tiene ajustes fechados hasta 2029."""
    assert elegido(FILAS)["training"]["carbs"] == 80


def test_el_desempate_entre_dos_del_mismo_dia_es_la_fila_mas_nueva():
    filas = FILAS + [{"id": "d", "client_id": CLIENTE, "effective_date": "2026-07-31",
                      "created_at": "2026-08-06T09:00:00+00:00", "training": {"carbs": 85}}]
    assert elegido(filas)["training"]["carbs"] == 85


def test_sin_historial_no_hay_ultimo():
    assert elegido([]) is None


def test_si_todo_esta_por_delante_se_coge_el_primero():
    """Un cliente al que solo se le ha programado: mejor su ajuste futuro que nada."""
    futuros = [f for f in FILAS if f["effective_date"] > "2026-08-12"]
    assert elegido(futuros)["effective_date"] == "2029-01-08"


def test_las_filas_hechas_en_la_app_no_traen_vigencia_y_valen_igual():
    """Las 9 que no vinieron de Calma: su `created_at` ES el día del ajuste."""
    filas = [{"id": "app", "client_id": CLIENTE, "created_at": "2026-08-11T10:00:00+00:00",
              "training": {"carbs": 120}, "origen": "coach"}]
    assert elegido(filas)["training"]["carbs"] == 120
