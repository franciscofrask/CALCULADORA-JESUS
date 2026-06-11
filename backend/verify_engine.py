from calma_engine import calcular_macros_efectivos

cases = [
    ("Lomo cocido (sin marca) H=2.0/100g -> NO cuenta", 16.0, 2.0, 4.0, "2.1", 312, False),
    ("Lomo cocido Hacendado H=2.19/100g -> SI cuenta", 16.3, 2.19, 3.5, "2.1", 306, True),
    ("Fiambre jamon pavo Dia H=2.0/100g -> NO cuenta", 14.0, 2.0, 4.0, "2.1", 357, False),
    ("Jamón braseado Noel H=0/100g G>3 -> NO H", 18.0, 0.0, 5.2, "2.1", 277, False),
]

for desc, p, h, g, cat, qty, h_expected in cases:
    r = calcular_macros_efectivos(p, h, g, cat, qty)
    h_ok = "OK" if r["hidratos_cuenta"] == h_expected else "FAIL"
    print(f"[{h_ok}] {desc}")
    print(f"       P={r['proteina_efectiva']}g H={r['hidratos_efectivos']}g G={r['grasa_efectiva']}g | H_cuenta={r['hidratos_cuenta']}")
