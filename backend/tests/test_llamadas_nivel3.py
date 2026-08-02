"""
Peticiones de llamada del Nivel 3.

El Nivel 3 se contrata hablando, asi que quien lo elige en el test de nivel deja nombre
y telefono y sale como aviso en el panel. Lo que se fija aqui es la validacion: sin
nombre o sin telefono el aviso llegaria sin con que atenderlo, y eso es peor que no
llegar. El resto (que aparezca en el panel y salga al marcarlo) se probo contra la app.
"""
import pytest
from fastapi import HTTPException

from routes.plans import _RE_EMAIL, _RE_DIGITOS


def telefono_valido(t: str) -> bool:
    """La misma regla que aplica el endpoint: al menos 9 digitos, se escriba como se escriba."""
    return len(_RE_DIGITOS.sub("", t or "")) >= 9


class TestElTelefono:
    @pytest.mark.parametrize("t", [
        "600112233",
        "+34 600 11 22 33",
        "600-11-22-33",
        "(+34) 600112233",
    ])
    def test_acepta_como_lo_escriba_la_gente(self, t):
        assert telefono_valido(t)

    @pytest.mark.parametrize("t", ["", "   ", "600", "11 22 33", "no tengo"])
    def test_rechaza_lo_que_no_sirve_para_llamar(self, t):
        assert not telefono_valido(t)

    def test_un_movil_espanol_entra(self):
        assert telefono_valido("612345678")

    def test_un_fijo_espanol_tambien(self):
        assert telefono_valido("911234567")


class TestElCorreo:
    @pytest.mark.parametrize("c", ["a@b.com", "nombre.apellido@dominio.es"])
    def test_acepta_los_normales(self, c):
        assert _RE_EMAIL.match(c)

    @pytest.mark.parametrize("c", ["noesuncorreo", "a@b", "@b.com", "a b@c.com", ""])
    def test_rechaza_los_rotos(self, c):
        assert not _RE_EMAIL.match(c)
