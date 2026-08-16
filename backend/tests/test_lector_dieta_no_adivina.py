"""
El lector de la dieta del alta no se inventa lo que come el cliente.

Salió probando el cuestionario: escribí «nueces» y la app entendió «Leche de nuez
(Borges)», y «ensalada» acabó en «Ensalada gourmet maxi (Carrefour)». Un fruto seco
convertido en bebida vegetal cambia la grasa del día de 19 g a 81 g, que es con lo que se
calculan sus macros de partida.

La causa era de una letra: quien lee la frase devuelve el singular («nueces» -> «nuez»),
el catálogo guarda «Nueces», y buscando «nuez» eso no aparecía; el único resultado era la
leche. Las dos reglas que se fijan aquí:

  1. se busca también la otra forma, singular o plural,
  2. si solo hay marcas, o el genérico ni menciona lo que escribió, NO se adivina.

La 2 es la regla de la casa para el asistente ("los términos genéricos con tipos dispares
no se adivinan, se preguntan"), aplicada donde no hay a quién preguntar: lo que no se
entiende se le devuelve para que lo corrija.
"""
import asyncio

import pytest

from core.lectura_dieta import _habla_de_lo_mismo, _variantes


# ── El singular y el plural ──────────────────────────────────────────────────

@pytest.mark.parametrize("palabra,esperada", [
    ("nuez", "nueces"),        # la z pasa a c
    ("pez", "peces"),
    ("verdura", "verduras"),   # vocal: +s
    ("yogur", "yogures"),      # consonante: +es
])
def test_del_singular_sale_el_plural(palabra, esperada):
    assert esperada in _variantes(palabra)


@pytest.mark.parametrize("palabra,esperada", [
    ("nueces", "nuez"),
    ("verduras", "verdura"),
    ("huevos", "huevo"),
])
def test_del_plural_sale_el_singular(palabra, esperada):
    assert esperada in _variantes(palabra)


def test_no_se_inventan_plurales_que_no_existen():
    """«nuezes» no es una palabra: buscarla no rompe nada, pero ensucia."""
    assert "nuezes" not in _variantes("nuez")


def test_una_palabra_de_dos_letras_se_deja_en_paz():
    assert _variantes("ok") == ["ok"]


# ── Que la ficha hable de lo que el cliente escribió ─────────────────────────

def test_la_proteina_de_suero_no_es_proteina_de_soja():
    """Comparten «proteína», que es justo la palabra que NO distingue."""
    assert not _habla_de_lo_mismo("proteina de suero", "Proteina de soja")


def test_la_pechuga_de_pollo_si_es_pollo_asado():
    """Lo que distingue va al final: no se puede ser tan estricto que rechace esto."""
    assert _habla_de_lo_mismo("pechuga de pollo", "Pollo asado")


def test_la_nuez_es_nueces():
    assert _habla_de_lo_mismo("nuez", "Nueces")


def test_la_leche_de_nuez_menciona_la_nuez_y_aun_asi_no_se_elige():
    """EL CASO QUE LO DESTAPÓ, y el matiz importante: esta regla NO lo salva. «Leche de
    nuez» sí menciona la nuez, así que aquí pasa; lo que impide elegirla es que es una
    MARCA y, al buscar también el plural, aparece el genérico «Nueces». Las dos piezas
    hacen falta, y por eso se comprueban las dos (ver el test de abajo)."""
    assert _habla_de_lo_mismo("nueces", "Leche de nuez (Borges)")


class _CatalogoDeMentira:
    """Lo que devolvía el catálogo de verdad el 16-08, medido: buscando «nuez» solo salía la
    leche de marca; el genérico solo aparece con el plural."""

    async def search_foods(self, termino, limit=6):
        return {
            "nuez": [{"nombre": "Leche de nuez (Borges)", "url": "https://..."}],
            "nueces": [{"nombre": "Nueces"}, {"nombre": "Nueces de macadamia"}],
            "ensalada": [{"nombre": "Ensalada gourmet maxi (Carrefour)", "url": "https://..."}],
        }.get(termino.lower(), [])



def test_buscando_el_plural_aparece_el_fruto_seco():
    from core.lectura_dieta import _buscar_con_variantes

    res = asyncio.run(_buscar_con_variantes(_CatalogoDeMentira(), "nuez"))
    assert any(a["nombre"] == "Nueces" and not a.get("url") for a in res), (
        "sigue sin encontrar el genérico: el cliente vuelve a desayunar bebida vegetal")



def test_si_solo_hay_marcas_se_devuelven_para_preguntar():
    """«ensalada» solo tiene marcas en el catálogo. Se devuelven -- quien llama decide --,
    y el lector las manda a «esto no lo he entendido» en vez de elegir una."""
    from core.lectura_dieta import _buscar_con_variantes

    res = asyncio.run(_buscar_con_variantes(_CatalogoDeMentira(), "ensalada"))
    assert res and all(a.get("url") for a in res)


def test_sin_palabras_utiles_no_se_bloquea_nada():
    """Si el término no tiene ninguna palabra larga, no se puede juzgar: se deja pasar y
    manda la preferencia por el genérico, como antes."""
    assert _habla_de_lo_mismo("te", "Té verde")
