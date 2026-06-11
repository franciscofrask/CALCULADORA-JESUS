from calma_engine import calcular_macros_efectivos

# Fiambre jamon pavo Dia: P=14, H=2, G=4 per 100g, cat 2.1
r = calcular_macros_efectivos(14.0, 2.0, 4.0, '2.1', 100)
p100 = r['proteina_efectiva']
h100 = r['hidratos_efectivos']
g100 = r['grasa_efectiva']
print("Por 100g (Calma method):")
print(f"  P={p100} H={h100} G={g100}")
print(f"  Calma muestra: '14 proteinas 4 grasas' -> match={p100==14.0 and h100==0.0 and g100==4.0}")

# Necesita a minimo=25g
r25 = calcular_macros_efectivos(14.0, 2.0, 4.0, '2.1', 25)
p25 = r25['proteina_efectiva']
g25 = r25['grasa_efectiva']
print("\nNecesita (a minimo=25g):")
print(f"  P={p25}g G={g25}g")
print(f"  Calma muestra: '3.5g proteinas / 1g grasas' -> match={p25==3.5 and g25==1.0}")
