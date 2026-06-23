"""
Tests de paridad con Calma para los gaps cerrados (lógica de backend).
Verifica contra valores conocidos del bundle de Calma. Ejecutar:
    PYTHONIOENCODING=utf-8 python test_calma_gaps.py
"""
import asyncio
import copy

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK  {name}")
    else:
        FAIL += 1
        print(f"  XX  {name}  {detail}")


# ── #5 Hidratos <30 + escenarios 4-comidas (z/J/W exactas) ──────────────────
def test_distribution():
    from macro_distribution import distribuir_macros as D
    base = dict(p_peri=40, h_peri=30, p_descanso=180, h_descanso=200, g_descanso=65,
                tipo_dia="entrenamiento", num_comidas=4, opcion_peri="intra_post")

    # #5: H<30 -> todo el hidrato al post (s==a+1). h=25, momento1 -> C2=25, resto 0
    r = D(p_entreno=180, h_entreno=25, g_entreno=65, momento_entreno=1, **base)
    c = r["comidas"]
    check("#5 H<30 todo al post (C2=25)", c["C2"]["H"] == 25 and c["C1"]["H"] == 0 and c["C3"]["H"] == 0 and c["C4"]["H"] == 0, c)

    # 30<=H<50: post H-10, secundaria 10. h=40 momento2 -> C3=30, C2=10
    r = D(p_entreno=180, h_entreno=40, g_entreno=65, momento_entreno=2, **base)
    c = r["comidas"]
    check("#5 30<=H<50 (C3=30,C2=10)", c["C3"]["H"] == 30 and c["C2"]["H"] == 10 and c["C1"]["H"] == 0 and c["C4"]["H"] == 0, c)

    # #13: 4 comidas z exacta. Escenario 2 (100-150H) momento 0 -> J[0]=[.36,.18,.1,.36]
    r = D(p_entreno=180, h_entreno=120, g_entreno=65, momento_entreno=0, **base)
    c = r["comidas"]
    check("#13 z/J exacta H momento0 (43.2/21.6/12/43.2)",
          c["C1"]["H"] == 43.2 and c["C2"]["H"] == 21.6 and c["C3"]["H"] == 12.0 and c["C4"]["H"] == 43.2, c)
    # proteínas z[0]=[.25,.25,.2,.3] -> 45/45/36/54
    check("#13 z proteínas momento0 (45/45/36/54)",
          c["C1"]["P"] == 45 and c["C2"]["P"] == 45 and c["C3"]["P"] == 36 and c["C4"]["P"] == 54, c)


# ── #12 Peri options (4 modos oficiales) ────────────────────────────────────
def test_peri():
    from macro_distribution import _calcular_periworkout as P
    r = P(40, 30, "intra_post")
    check("#12 intra_post: Intra 8/9, Post 32/21",
          r["Intra"]["P"] == 8 and r["Intra"]["H"] == 9 and r["Post"]["P"] == 32 and r["Post"]["H"] == 21, r)
    r = P(40, 30, "solo_post")
    check("#12 solo_post: Post 100%, sin Intra", r["Post"]["P"] == 40 and r["Post"]["H"] == 30 and "Intra" not in r, r)
    # modo 3 (oficial): solo intra 25%P/35%H, resto (75%/65%) a las comidas, sin Post
    r = P(40, 30, "solo_intra")
    check("#12 solo_intra: Intra 10/10.5, resto a comidas, sin Post",
          r["Intra"]["P"] == 10 and r["Intra"]["H"] == 10.5 and "Post" not in r
          and round(r["extra_comidas"]["P"]) == 30, r)
    # modo 4 (oficial): sin intra/post, todo el peri a las comidas
    r = P(40, 30, "sin_peri")
    check("#12 sin_peri: sin Intra/Post, todo a comidas",
          "Intra" not in r and "Post" not in r and r["extra_comidas"]["P"] == 40 and r["extra_comidas"]["H"] == 30, r)


# ── #9 Modo comida única ────────────────────────────────────────────────────
def test_single_meal():
    from macro_distribution import distribuir_macros as D
    r = D(p_entreno=180, h_entreno=250, g_entreno=65, p_peri=40, h_peri=30,
          p_descanso=180, h_descanso=200, g_descanso=65, tipo_dia="entrenamiento",
          num_comidas=4, momento_entreno=1, opcion_peri="intra_post", single_meal=True)
    c = r["comidas"]
    check("#9 single: 1 comida = día completo", list(c.keys()) == ["C1"] and c["C1"] == {"P": 180, "H": 250, "G": 65}, c)
    check("#9 single: peri aparte", r["periworkout"].get("Post", {}).get("P") == 32, r["periworkout"])
    check("#9 single: config.single_meal", r["config"]["single_meal"] is True, r["config"])


# ── #4 Resolver de macros por fecha ─────────────────────────────────────────
async def test_macro_resolver():
    import routes.calculator as rc
    prof = {"id": "C1", "macros_training": {"protein": 200}, "macros_rest": {"protein": 150},
            "macros_periworkout": {"protein": 40}}
    entries = [
        {"client_id": "C1", "effective_date": "2026-05-01", "new_training": {"protein": 180}, "new_rest": {"protein": 140}, "peri": {"protein": 35}, "created_at": "2026-05-01T00:00"},
        {"client_id": "C1", "effective_date": "2026-06-10", "new_training": {"protein": 210}, "new_rest": {"protein": 160}, "peri": {"protein": 45}, "created_at": "2026-06-10T00:00"},
    ]

    class FakeCur:
        def __init__(s, d): s.d = d
        async def to_list(s, n): return s.d

    class FakeColl:
        def __init__(s, d): s.d = d
        def find(s, q, proj): return FakeCur(s.d)

    orig = rc.db.macro_history
    rc.db.macro_history = FakeColl(entries)
    try:
        t, _, p = await rc._resolve_macros_for_date(prof, "2026-04-20")
        check("#4 antes del 1er cambio -> más antigua (180/35)", t["protein"] == 180 and p["protein"] == 35)
        t, _, _ = await rc._resolve_macros_for_date(prof, "2026-05-15")
        check("#4 entre cambios -> versión 1-may (180)", t["protein"] == 180)
        t, _, p = await rc._resolve_macros_for_date(prof, "2026-06-13")
        check("#4 post-cambio -> versión 10-jun (210/45)", t["protein"] == 210 and p["protein"] == 45)
        t, _, _ = await rc._resolve_macros_for_date(prof, None)
        check("#4 sin fecha -> perfil actual (200)", t["protein"] == 200)
    finally:
        rc.db.macro_history = orig


# ── #11 Búsqueda all-words (cada palabra substring, normalizado) ────────────
async def test_search():
    from calculator import buscar_alimentos
    from core.database import db
    r = await buscar_alimentos(db, query="crema arroz", limit=20)
    check("#11 'crema arroz' matchea 'Crema de arroz...'", any("crema de arroz" in a["nombre"].lower() for a in r), f"{len(r)} results")
    r = await buscar_alimentos(db, query="arroz integral", limit=30)
    check("#11 'arroz integral' all-words (no contiguo)", any("integral" in a["nombre"].lower() and "arroz" in a["nombre"].lower() for a in r))
    r = await buscar_alimentos(db, query="platano", limit=10)
    check("#11 'platano' sin acento matchea 'Plátano'", any("plátano" in a["nombre"].lower() or "platano" in a["nombre"].lower() for a in r))


# ── #6/orden: sugerencias por diferenciaDeMacros ascendente ─────────────────
async def test_suggest_order():
    from calculator import buscar_alimentos
    from core.database import db
    import calma_suggest as cs
    foods = await buscar_alimentos(db, query="arroz", limit=4000)
    rem = {"proteinas": 47.5, "hidratos": 36.3, "grasas": 12.0}
    out = []
    for a in foods:
        cs.aplicar_regla_macros(a)
        cant = cs.ajustar_cantidad(a, rem)
        if cant <= 0:
            continue
        m = cs.macros_at(a, cant)
        out.append((cs.diferencia_de_macros(m, rem), a["nombre"]))
    out.sort(key=lambda x: (x[0], x[1]))
    top = out[0][1] if out else ""
    check("#6 orden diferencia: tikka #1 en 'arroz'", "tikka" in top.lower(), top)


async def main():
    print("== Distribución (#5/#13) =="); test_distribution()
    print("== Peri (#12) =="); test_peri()
    print("== Comida única (#9) =="); test_single_meal()
    print("== Macros por fecha (#4) =="); await test_macro_resolver()
    print("== Búsqueda (#11) =="); await test_search()
    print("== Orden sugerencias (#6) =="); await test_suggest_order()
    print("=" * 50)
    print(f"RESULTADO: {PASS} OK / {FAIL} FAIL de {PASS + FAIL}")


if __name__ == "__main__":
    asyncio.run(main())
