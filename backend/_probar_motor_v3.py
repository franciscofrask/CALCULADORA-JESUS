"""
Comprueba el motor contra las reglas del doc de Jesus del 29-07-2026.
Cada caso dice que regla verifica. Ejecutar: venv/Scripts/python.exe _probar_motor_v3.py
"""
from macro_engine import calcular_macros_v2, BANDAS_PERI, SUELO_HC_COMIDAS_ENTRENO

fallos = []


def comprobar(titulo, condicion, detalle=""):
    print(f"  {'OK  ' if condicion else 'FALLA'} {titulo}" + (f"   [{detalle}]" if detalle else ""))
    if not condicion:
        fallos.append(titulo)


def m(r):
    """Atajo: (hc_entreno, peri, hc_descanso, grasa_entreno, grasa_descanso, proteina_descanso)."""
    x = r["macros"]
    return (x["entreno"]["hidratos"], x["perientreno"]["hidratos"], x["descanso"]["hidratos"],
            x["entreno"]["grasa"], x["descanso"]["grasa"], x["descanso"]["proteina"])


print("\n1) DEPORTE EXTRA: +10% en definicion, +20% en volumen (solo descanso)")
base_def = calcular_macros_v2(80, "hombre", 15, "definicion")
con_dep_def = calcular_macros_v2(80, "hombre", 15, "definicion", deporte_extra=True)
base_vol = calcular_macros_v2(80, "hombre", 15, "volumen")
con_dep_vol = calcular_macros_v2(80, "hombre", 15, "volumen", deporte_extra=True)
subida_def = m(con_dep_def)[2] / m(base_def)[2]
subida_vol = m(con_dep_vol)[2] / m(base_vol)[2]
comprobar("definicion sube ~10% el descanso", 1.05 < subida_def < 1.15, f"x{subida_def:.3f}")
comprobar("volumen sube ~20% el descanso", 1.15 < subida_vol < 1.25, f"x{subida_vol:.3f}")
# El entreno SI puede subir aqui, y no es un error: en la tabla el descanso va pegado al entreno,
# asi que el +10% lo pasa y la regla dura obliga a subir el entreno hasta igualarlo. Lo que se
# comprueba es que el entreno solo se mueve por esa razon, nunca por el modificador en si.
subio_entreno = m(con_dep_def)[0] > m(base_def)[0]
nivelado = any(d.get("paso") == "nivelar_descanso" for d in con_dep_def["desglose"])
comprobar("el entreno solo sube si lo obliga la regla dura", subio_entreno == nivelado,
          f"entreno {m(base_def)[0]} -> {m(con_dep_def)[0]}, nivelado={nivelado}")

print("\n2) 'ENGORDO LO NORMAL' con grasa <= 20% ahora TAMBIEN sube +20%")
normal_15 = calcular_macros_v2(80, "hombre", 15, "definicion", facilidad_engordar="normal")
normal_25 = calcular_macros_v2(80, "hombre", 25, "definicion", facilidad_engordar="normal")
casi_15 = calcular_macros_v2(80, "hombre", 15, "definicion", facilidad_engordar="casi_no")
comprobar("'normal' con 15% sube", m(normal_15)[0] > m(base_def)[0],
          f"{m(base_def)[0]} -> {m(normal_15)[0]}")
comprobar("'normal' sube lo mismo que 'casi_no'", m(normal_15)[0] == m(casi_15)[0])
base_25 = calcular_macros_v2(80, "hombre", 25, "definicion")
comprobar("'normal' con 25% NO sube", m(normal_25)[0] == m(base_25)[0])

print("\n3) VETO: 'engordo enseguida' anula cualquier subida")
veto = calcular_macros_v2(80, "hombre", 15, "volumen", facilidad_engordar="enseguida",
                          actividad_diaria="muy_activo", deporte_extra=True)
comprobar("con veto queda igual que la tabla", m(veto)[:3] == m(base_vol)[:3],
          f"{m(veto)[:3]} vs {m(base_vol)[:3]}")

print("\n4) REGLA DURA: el descanso nunca por encima del entreno")
duro = calcular_macros_v2(60, "hombre", 10, "volumen", deporte_extra=True, actividad_diaria="muy_activo",
                         facilidad_engordar="casi_no")
comprobar("descanso <= entreno", m(duro)[2] <= m(duro)[0], f"entreno {m(duro)[0]} / descanso {m(duro)[2]}")

print("\n5) TRT: se guarda pero NO se aplica (pendiente de Jesus)")
sin_trt = calcular_macros_v2(80, "hombre", 15, "definicion")
con_trt = calcular_macros_v2(80, "hombre", 15, "definicion", farmacologia=True)
comprobar("la proteina de descanso no cambia", m(con_trt)[5] == m(sin_trt)[5],
          f"{m(sin_trt)[5]} -> {m(con_trt)[5]}")
paso = [d for d in con_trt["desglose"] if d.get("paso") == "farmacologia"]
comprobar("queda registrado como no aplicado", bool(paso) and paso[0]["estado"] == "no_aplicado")

print("\n6) BANDAS DE PERI nuevas: <300->40, 300-350->50, 350-400->60, 400-450->75, >450->90")
comprobar("la tabla de bandas es la del doc",
          BANDAS_PERI[0] == (300, 40) and BANDAS_PERI[1] == (350, 50) and BANDAS_PERI[2] == (400, 60),
          str(BANDAS_PERI[:3]))
for total, esperado in ((280, 40), (320, 50), (380, 60), (430, 75), (500, 90)):
    r = calcular_macros_v2(90, "hombre", 12, "volumen", como_va="bien",
                           dieta_reportada={"hc_entreno": total})
    comprobar(f"X={total} -> peri {esperado}", m(r)[1] == esperado, f"peri {m(r)[1]}")

print("\n7) MATRIZ DE DEFINICION")
#  T de referencia para este cliente
t_ref = calcular_macros_v2(85, "hombre", 18, "definicion")
T = m(t_ref)[0] + m(t_ref)[1]
print(f"  (T = {T} g de hidratos entreno + peri)")
alto = T + 120
d_bien = calcular_macros_v2(85, "hombre", 18, "definicion", como_va="bien",
                           dieta_reportada={"hc_entreno": alto})
comprobar("'bajando bien' con X>T: se le deja X", abs((m(d_bien)[0] + m(d_bien)[1]) - alto) <= 5,
          f"{m(d_bien)[0] + m(d_bien)[1]} vs X={alto}")
d_lento = calcular_macros_v2(85, "hombre", 18, "definicion", como_va="lento",
                             dieta_reportada={"hc_entreno": alto})
comprobar("'bajando lento' con X>T: manda la tabla", (m(d_lento)[0] + m(d_lento)[1]) == T,
          f"{m(d_lento)[0] + m(d_lento)[1]} vs T={T}")
d_mant = calcular_macros_v2(85, "hombre", 18, "definicion", como_va="mantengo",
                            dieta_reportada={"hc_entreno": alto})
comprobar("'me mantengo' con X>T: el 75% de X",
          abs((m(d_mant)[0] + m(d_mant)[1]) - alto * 0.75) <= 5,
          f"{m(d_mant)[0] + m(d_mant)[1]} vs 75% de X = {alto * 0.75:.0f}")

print("\n8) DEFINICION con X < T: peri 15, descanso -20%, grasa 50/60")
bajo = max(T - 60, 90)
d_bajo = calcular_macros_v2(85, "hombre", 18, "definicion", como_va="lento",
                            dieta_reportada={"hc_entreno": bajo})
hc_e, peri, hc_d, gr_e, gr_d, _ = m(d_bajo)
comprobar("peri 15", peri == 15, f"peri {peri}")
comprobar("grasa 50 en entreno y 60 en descanso", gr_e == 50 and gr_d == 60, f"{gr_e}/{gr_d}")
comprobar("descanso ~20% por debajo de las comidas", abs(hc_d - hc_e * 0.8) <= 5, f"{hc_e} -> {hc_d}")

print("\n9) MATRIZ DE VOLUMEN: con X<=T, 'lento'/'mantengo'/'bajando' mandan la tabla")
t_vol = calcular_macros_v2(85, "hombre", 12, "volumen")
Tv = m(t_vol)[0] + m(t_vol)[1]
bajo_v = Tv - 80
for clave in ("lento", "mantengo", "bajando"):
    r = calcular_macros_v2(85, "hombre", 12, "volumen", como_va=clave,
                           dieta_reportada={"hc_entreno": bajo_v})
    comprobar(f"'{clave}' con X<=T: la tabla", (m(r)[0] + m(r)[1]) == Tv,
              f"{m(r)[0] + m(r)[1]} vs T={Tv}")
for clave in ("bien", "mucha_grasa"):
    r = calcular_macros_v2(85, "hombre", 12, "volumen", como_va=clave,
                           dieta_reportada={"hc_entreno": bajo_v})
    comprobar(f"'{clave}' con X<=T: se le pone X", abs((m(r)[0] + m(r)[1]) - bajo_v) <= 5,
              f"{m(r)[0] + m(r)[1]} vs X={bajo_v}")

print("\n10) GRASA SEGUN LA DIETA QUE TRAE: <=60->60, 60-90->70, >=90->80")
for grasa, esperado in ((55, 60), (75, 70), (110, 80)):
    r = calcular_macros_v2(85, "hombre", 12, "volumen", como_va="bien",
                           dieta_reportada={"hc_entreno": 380, "grasa_entreno": grasa})
    comprobar(f"trae {grasa} g -> {esperado}", m(r)[3] == esperado and m(r)[4] == esperado,
              f"{m(r)[3]}/{m(r)[4]}")

print("\n11) SUELOS: 60 g de comidas en entreno (75 con el peri) y 50 de grasa")
comprobar("el suelo de comidas es 60", SUELO_HC_COMIDAS_ENTRENO == 60, str(SUELO_HC_COMIDAS_ENTRENO))
suelo = calcular_macros_v2(50, "mujer", 30, "definicion", como_va="lento",
                           dieta_reportada={"hc_entreno": 80})
comprobar("no baja de 60 en comidas", m(suelo)[0] >= 60, f"{m(suelo)[0]}")
comprobar("no baja de 50 la grasa", m(suelo)[3] >= 50 and m(suelo)[4] >= 50, f"{m(suelo)[3]}/{m(suelo)[4]}")

print("\n12) REDONDEO a multiplos de 5")
todos = []
for r in (base_def, con_dep_vol, d_bien, d_bajo, suelo):
    todos += list(m(r))
comprobar("todo multiplo de 5", all(v % 5 == 0 for v in todos))

print("\n" + "=" * 64)
if fallos:
    print(f"{len(fallos)} COMPROBACIONES FALLAN:")
    for f in fallos:
        print("  -", f)
else:
    print("TODAS LAS COMPROBACIONES PASAN")
print("=" * 64)
