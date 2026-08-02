"""
Los avisos que la app manda al cliente (especificacion 31-07-2026, parte 9).

Lo que se fija aqui son las tres reglas que hacen que un aviso ayude en vez de molestar:

  - maximo UNA condicionada por semana,
  - ninguna repetida por entrar varias veces en la app,
  - y ninguna escrita desde la exigencia.

La ultima parece de estilo y no lo es: "este cliente lleva años oyendo que no tiene
fuerza de voluntad; si la app se une a ese coro, la desinstala".
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.avisos_cliente import (
    DIAS_ENTRE_CONDICIONADAS,
    avisos_condicionados,
    avisos_de_calendario,
    elegir_avisos,
)

AHORA = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)


def _claves(avisos):
    return [a["clave"].split(":")[0] for a in avisos]


class TestUnaPorSemanaYNoMas:
    """"maximo una notificacion por semana que no sea de calendario"."""

    def test_aunque_se_cumplan_todas_sale_una(self):
        cond = avisos_condicionados(
            ahora=AHORA, dias_sin_peso=20, dias_sin_dieta=15, semanas_sin_ajustar=6,
            reporte_sin_fotos=True, estancado=True, dias_sin_entrar=30)
        assert len(cond) == 6, "se detectan todas"
        elegidos = elegir_avisos([], cond, set(), None, AHORA)
        assert len(elegidos) == 1, "pero solo se manda una"

    def test_las_de_calendario_no_gastan_el_cupo(self):
        cal = avisos_de_calendario(
            perfil={"ajuste_macros_completado": True, "week": 11, "id": "c1"},
            ahora=AHORA, semanas_ciclo=12,
            proximo_ajuste=AHORA + timedelta(days=6))
        cond = avisos_condicionados(ahora=AHORA, dias_sin_peso=10)
        elegidos = elegir_avisos(cal, cond, set(), None, AHORA)
        assert len(elegidos) == len(cal) + 1

    def test_si_ya_tuvo_una_esta_semana_no_le_llega_otra(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_peso=10, dias_sin_dieta=10)
        hace_dos_dias = (AHORA - timedelta(days=2)).isoformat()
        assert elegir_avisos([], cond, set(), hace_dos_dias, AHORA) == []

    def test_pasada_la_semana_vuelve_a_poder(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_peso=10)
        hace_ocho_dias = (AHORA - timedelta(days=DIAS_ENTRE_CONDICIONADAS + 1)).isoformat()
        assert len(elegir_avisos([], cond, set(), hace_ocho_dias, AHORA)) == 1

    def test_el_tope_no_frena_las_de_calendario(self):
        cal = avisos_de_calendario(perfil={"ajuste_macros_completado": True}, ahora=AHORA,
                                   arranque=AHORA + timedelta(days=1))
        ayer = (AHORA - timedelta(days=1)).isoformat()
        assert len(elegir_avisos(cal, [], set(), ayer, AHORA)) == 1


class TestNoSeRepiten:
    def test_entrar_diez_veces_no_genera_diez_avisos(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_peso=10)
        ya = {cond[0]["clave"]}
        assert elegir_avisos([], cond, ya, None, AHORA) == []

    def test_la_clave_lleva_la_semana_para_poder_repetirse_mas_adelante(self):
        de_esta = avisos_condicionados(ahora=AHORA, dias_sin_peso=10)[0]["clave"]
        otra_semana = AHORA + timedelta(days=14)
        de_otra = avisos_condicionados(ahora=otra_semana, dias_sin_peso=10)[0]["clave"]
        assert de_esta != de_otra

    def test_el_aviso_de_una_fecha_concreta_no_se_repite(self):
        arranque = AHORA + timedelta(days=1)
        a = avisos_de_calendario(perfil={"ajuste_macros_completado": True}, ahora=AHORA,
                                 arranque=arranque)[0]
        assert str(arranque.date()) in a["clave"]


class TestPrioridad:
    """Si se cumplen varias, la que sale tiene que ser la mas util."""

    def test_las_fotos_van_antes_que_el_peso(self):
        cond = avisos_condicionados(ahora=AHORA, reporte_sin_fotos=True, dias_sin_peso=10)
        assert _claves(cond)[0] == "sin_fotos"

    def test_los_macros_estancados_van_antes_que_registrar_dieta(self):
        cond = avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=4, dias_sin_dieta=10)
        assert _claves(cond)[0] == "sin_ajustar"

    def test_al_que_no_entra_se_le_avisa_el_ultimo(self):
        cond = avisos_condicionados(ahora=AHORA, dias_sin_entrar=30, dias_sin_peso=10,
                                    dias_sin_dieta=10)
        assert _claves(cond)[-1] == "sin_entrar"


class TestLosUmbrales:
    def test_seis_dias_sin_peso_todavia_no(self):
        assert avisos_condicionados(ahora=AHORA, dias_sin_peso=6) == []

    def test_siete_si(self):
        assert len(avisos_condicionados(ahora=AHORA, dias_sin_peso=7)) == 1

    def test_cuatro_dias_sin_dieta_todavia_no(self):
        assert avisos_condicionados(ahora=AHORA, dias_sin_dieta=4) == []

    def test_cinco_si(self):
        assert len(avisos_condicionados(ahora=AHORA, dias_sin_dieta=5)) == 1

    def test_una_semana_sin_ajustar_no_es_motivo(self):
        assert avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=1) == []

    def test_dos_semanas_si(self):
        a = avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=2)[0]
        assert "2 semanas" in a["titulo"]

    def test_trece_dias_sin_entrar_no(self):
        assert avisos_condicionados(ahora=AHORA, dias_sin_entrar=13) == []

    def test_sin_datos_no_inventa_avisos(self):
        assert avisos_condicionados(ahora=AHORA) == []


class TestCalendario:
    def test_los_macros_provisionales_avisan_a_las_dos_horas(self):
        perfil = {"created_at": (AHORA - timedelta(hours=2, minutes=1)).isoformat()}
        assert _claves(avisos_de_calendario(perfil=perfil, ahora=AHORA)) == ["macros_provisionales"]

    def test_antes_de_las_dos_horas_no(self):
        perfil = {"created_at": (AHORA - timedelta(minutes=30)).isoformat()}
        assert avisos_de_calendario(perfil=perfil, ahora=AHORA) == []

    def test_si_ya_los_ajusto_no_se_le_insiste(self):
        perfil = {"created_at": (AHORA - timedelta(days=3)).isoformat(),
                  "ajuste_macros_completado": True}
        assert avisos_de_calendario(perfil=perfil, ahora=AHORA) == []

    def test_el_domingo_de_antes_de_arrancar(self):
        a = avisos_de_calendario(perfil={"ajuste_macros_completado": True}, ahora=AHORA,
                                 arranque=AHORA + timedelta(days=1))
        assert a[0]["titulo"] == "Mañana empiezas"

    def test_dos_dias_antes_todavia_no(self):
        a = avisos_de_calendario(perfil={"ajuste_macros_completado": True}, ahora=AHORA,
                                 arranque=AHORA + timedelta(days=2))
        assert a == []

    def test_la_rutina_avisa_tres_dias_antes_no_el_dia_que_caduca(self):
        base = {"perfil": {"ajuste_macros_completado": True}, "ahora": AHORA}
        assert avisos_de_calendario(**base, rutina_caduca=AHORA + timedelta(days=3))
        assert avisos_de_calendario(**base, rutina_caduca=AHORA) == []

    def test_el_ajuste_avisa_a_seis_dias_y_el_dia(self):
        base = {"perfil": {"ajuste_macros_completado": True}, "ahora": AHORA}
        assert _claves(avisos_de_calendario(**base, proximo_ajuste=AHORA + timedelta(days=6))) == ["ajuste_pronto"]
        assert _claves(avisos_de_calendario(**base, proximo_ajuste=AHORA)) == ["ajuste_hoy"]
        assert avisos_de_calendario(**base, proximo_ajuste=AHORA + timedelta(days=3)) == []

    def test_la_semana_11_de_un_ciclo_de_12(self):
        perfil = {"ajuste_macros_completado": True, "week": 11, "id": "c1"}
        a = avisos_de_calendario(perfil=perfil, ahora=AHORA, semanas_ciclo=12)
        assert "acaba en una semana" in a[0]["titulo"]

    def test_en_la_semana_5_no(self):
        perfil = {"ajuste_macros_completado": True, "week": 5, "id": "c1"}
        assert avisos_de_calendario(perfil=perfil, ahora=AHORA, semanas_ciclo=12) == []


class TestElTono:
    """"todas escritas desde el alivio, no desde la exigencia"."""

    TODOS = (
        avisos_condicionados(ahora=AHORA, dias_sin_peso=30, dias_sin_dieta=30,
                             semanas_sin_ajustar=8, reporte_sin_fotos=True,
                             estancado=True, dias_sin_entrar=30)
        + avisos_de_calendario(perfil={"created_at": (AHORA - timedelta(days=1)).isoformat(),
                                       "week": 11, "id": "c1"},
                               ahora=AHORA, semanas_ciclo=12,
                               arranque=AHORA + timedelta(days=1),
                               proximo_ajuste=AHORA,
                               rutina_caduca=AHORA + timedelta(days=3))
    )

    @pytest.mark.parametrize("prohibida", [
        "fuerza de voluntad", "excusa", "vago", "deberías", "deberias",
        "no has", "otra vez", "te lo dijimos", "incumpl", "fallado", "abandonar",
    ])
    def test_ninguno_regaña(self, prohibida):
        for a in self.TODOS:
            texto = f"{a['titulo']} {a.get('cuerpo') or ''}".lower()
            assert prohibida not in texto, f"«{a['titulo']}» suena a reproche"

    def test_la_de_los_macros_es_factual_y_va_directa(self):
        """La unica que el documento quiere directa: es un dato, no un juicio."""
        a = avisos_condicionados(ahora=AHORA, semanas_sin_ajustar=5)[0]
        assert a["titulo"] == "Llevas 5 semanas con los mismos macros"

    def test_al_que_lleva_dos_semanas_fuera_se_le_deja_la_puerta_abierta(self):
        a = avisos_condicionados(ahora=AHORA, dias_sin_entrar=20)[0]
        assert a["titulo"] == "Tu plan sigue aquí"
        assert "cuando quieras" in (a["cuerpo"] or "")

    def test_todos_llevan_a_algun_sitio(self):
        """Un aviso sin sitio al que ir es solo ruido."""
        for a in self.TODOS:
            assert a.get("link"), f"«{a['titulo']}» no lleva a ninguna parte"
