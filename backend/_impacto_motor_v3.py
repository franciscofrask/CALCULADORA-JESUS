"""
Impacto real del motor nuevo (doc 29-07) sobre quien SI paso el cuestionario.
Recalcula con las respuestas guardadas en quiz_respuestas y compara con lo que se le dio.
Solo LEE de dev.
"""
import asyncio
from collections import Counter
from core.database import db
from macro_engine import calcular_macros_v2


def tot(macros):
    e = macros.get("entreno", {})
    p = macros.get("perientreno", {})
    d = macros.get("descanso", {})
    return (int(e.get("hidratos", 0)) + int(p.get("hidratos", 0)),
            int(d.get("hidratos", 0)),
            int(e.get("grasa", 0)),
            int(d.get("grasa", 0)))


async def r():
    docs = await db.quiz_respuestas.find({}, {"_id": 0}).to_list(500)
    print(f"{len(docs)} personas han pasado el cuestionario\n")

    iguales = cambian = fallos = 0
    con_dieta = []
    motivos = Counter()
    detalle = []

    for q in docs:
        resp = q.get("respuestas") or {}
        try:
            nuevo = calcular_macros_v2(
                peso=float(q["peso"]), sexo=q["sexo"],
                porcentaje_graso=float(q["porcentaje_graso"]), objetivo=q["objetivo"],
                actividad_diaria=resp.get("actividad_diaria"),
                deporte_extra=resp.get("deporte_extra"),
                facilidad_engordar=resp.get("facilidad_engordar"),
            )
        except Exception as e:
            fallos += 1
            continue

        # Quien reporto su dieta no es comparable: su resultado original incluye unos hidratos
        # reportados que no quedaron guardados en 'respuestas', asi que no se pueden reproducir.
        uso_dieta = any(p.get("paso") == "dieta_reportada" for p in (q.get("desglose") or []))
        if uso_dieta:
            con_dieta.append(q)
            continue

        antes = tot(q.get("macros_resultantes") or {})
        ahora = tot(nuevo["macros"])
        if antes == ahora:
            iguales += 1
        else:
            cambian += 1
            for paso in nuevo["desglose"]:
                if paso.get("estado") == "aplicado":
                    motivos[paso["paso"]] += 1
            if len(detalle) < 12:
                detalle.append((q["sexo"][:3], q["objetivo"][:3], q["peso"], q["porcentaje_graso"],
                                resp.get("facilidad_engordar"), resp.get("deporte_extra"), antes, ahora))

    comparables = cambian + iguales
    print(f"comparables (sin dieta reportada): {comparables}")
    print(f"   les cambia el resultado: {cambian}")
    print(f"   les queda igual:         {iguales}")
    print(f"con dieta reportada (no comparables): {len(con_dieta)}")
    if fallos:
        print(f"no se pudo recalcular:   {fallos}")
    print("\nmotivos del cambio:")
    for k, v in motivos.most_common():
        print(f"   {k}: {v}")
    print("\n  sexo obj  peso  %gr  engordar   dep   ANTES (e+peri, desc, grE, grD) -> AHORA")
    for s, o, pe, bf, fe, de, a, b in detalle:
        print(f"   {s}  {o}  {pe:5.1f} {bf:4.1f}  {str(fe):9s} {str(de):5s} {a} -> {b}")

asyncio.run(r())
