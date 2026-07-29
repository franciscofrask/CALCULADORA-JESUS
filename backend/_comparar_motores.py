"""
Mismo cliente por el motor de antes y por el de ahora, regla a regla.

Sirve para cualquier cambio futuro de reglas: se compara la version en git contra
la del disco y se ve que se mueve. Uso:
    venv/Scripts/python.exe _comparar_motores.py            (contra el commit anterior)
    REF=HEAD~5 venv/Scripts/python.exe _comparar_motores.py (contra otro punto)
"""
import os
import subprocess
import sys

REF = os.environ.get("REF", "HEAD~1")
_ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_motor_viejo.py")
try:
    volcado = subprocess.run(["git", "show", f"{REF}:backend/macro_engine.py"],
                             capture_output=True, text=True, check=True,
                             cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(_ruta, "w", encoding="utf-8") as fh:
        fh.write(volcado.stdout)
except Exception as e:
    print(f"No se ha podido sacar el motor de {REF}: {e}")
    sys.exit(1)

from _motor_viejo import calcular_macros_v2 as viejo   # noqa: E402
from macro_engine import calcular_macros_v2 as nuevo   # noqa: E402


def f(r):
    x = r["macros"]
    return (f"{x['entreno']['hidratos']}+{x['perientreno']['hidratos']}",
            x["descanso"]["hidratos"], x["entreno"]["grasa"], x["descanso"]["grasa"])


def fila(titulo, **kw):
    # El motor viejo no conoce 'como_va' (la pregunta es nueva): se le llama sin ella.
    kw_viejo = {k: v for k, v in kw.items() if k != "como_va"}
    v, n = f(viejo(**kw_viejo)), f(nuevo(**kw))
    marca = "  <-- CAMBIA" if v != n else ""
    print(f"  {titulo:46s}")
    print(f"     antes: HC entreno {v[0]:9s} descanso {v[1]:4} | grasa {v[2]}/{v[3]}")
    print(f"     ahora: HC entreno {n[0]:9s} descanso {n[1]:4} | grasa {n[2]}/{n[3]}{marca}")
    print()


print("\n=== 1. DEPORTE EXTRA ===")
fila("definicion, 80 kg, 15% (juega al padel)", peso=80, sexo="hombre", porcentaje_graso=15,
     objetivo="definicion", deporte_extra=True)
fila("volumen, 80 kg, 15% (juega al padel)", peso=80, sexo="hombre", porcentaje_graso=15,
     objetivo="volumen", deporte_extra=True)

print("=== 2. 'ENGORDO LO NORMAL' ===")
fila("definicion, 80 kg, 15%, 'engordo lo normal'", peso=80, sexo="hombre", porcentaje_graso=15,
     objetivo="definicion", facilidad_engordar="normal")
fila("el mismo pero con 25% de grasa", peso=80, sexo="hombre", porcentaje_graso=25,
     objetivo="definicion", facilidad_engordar="normal")

print("=== 3. TRT ===")
for r, quien in ((viejo, "antes"), (nuevo, "ahora")):
    x = r(peso=80, sexo="hombre", porcentaje_graso=15, objetivo="definicion", farmacologia=True)["macros"]
    print(f"  {quien}: proteina en descanso {x['descanso']['proteina']}")
print()

print("=== 4. BANDAS DE PERI (reporta 320 g de hidratos, volumen, va bien) ===")
fila("mismo caso", peso=90, sexo="hombre", porcentaje_graso=12, objetivo="volumen",
     como_va="bien", dieta_reportada={"hc_entreno": 320})

print("=== 5. SUELO DEL DIA DE ENTRENO (mujer 50 kg, 30%, come 80 g) ===")
fila("mismo caso", peso=50, sexo="mujer", porcentaje_graso=30, objetivo="definicion",
     como_va="lento", dieta_reportada={"hc_entreno": 80})

print("=== 6. GRASA SEGUN LA DIETA QUE TRAE (volumen, 380 g HC y 110 g de grasa) ===")
fila("mismo caso", peso=85, sexo="hombre", porcentaje_graso=12, objetivo="volumen",
     como_va="bien", dieta_reportada={"hc_entreno": 380, "grasa_entreno": 110})

print("=== 7. PASO 4: MISMA DIETA, DISTINTO 'COMO TE VA' (definicion, come 300 g) ===")
print("  El motor viejo daba el MISMO resultado en los cuatro casos:")
x = f(viejo(peso=85, sexo="hombre", porcentaje_graso=18, objetivo="definicion",
            dieta_reportada={"hc_entreno": 300}))
print(f"     antes (siempre): HC entreno {x[0]}  descanso {x[1]}\n")
print("  Ahora depende de como le esta funcionando:")
for clave, etiqueta in (("bien", "bajando a buen ritmo"), ("lento", "bajando muy lento"),
                        ("mantengo", "me mantengo"), ("cogiendo_peso", "cogiendo peso")):
    y = f(nuevo(peso=85, sexo="hombre", porcentaje_graso=18, objetivo="definicion",
                como_va=clave, dieta_reportada={"hc_entreno": 300}))
    print(f"     {etiqueta:22s} HC entreno {y[0]:9s} descanso {y[1]}")
