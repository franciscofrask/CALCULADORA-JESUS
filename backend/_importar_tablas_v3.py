"""
Importa "5 · TABLAS MACROS v3 (tablas operativas).csv" sobre macros_tables.json.

One-shot (18-07-2026). La v3 revisa sobre todo las tablas de MUJER (hc_e, hc_d,
pr_d en ~123 filas) y 1 fila de hombre. El CSV no trae algunas filas que si
existen en la tabla actual (hombre 120 kg bf 30-45, entre otras): esas se
CONSERVAN tal cual para no dejar combinaciones sin resultado.

Uso:  ./venv/Scripts/python.exe _importar_tablas_v3.py [--dry-run]
Deja backup en macros_tables.pre_v3.json.
"""

import csv
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE, "macros_tables.json")
BACKUP_PATH = os.path.join(BASE, "macros_tables.pre_v3.json")
CSV_PATH = r"C:\Users\Administrador\Downloads\5 · TABLAS MACROS v3 (tablas operativas).csv"

CSV_COLS = {
    "pr_e": "P_entreno", "hc_e": "H_entreno", "gr_e": "G_entreno",
    "pr_pe": "P_peri", "hc_pe": "H_peri",
    "pr_d": "P_descanso", "hc_d": "H_descanso", "gr_d": "G_descanso",
}


def leer_csv():
    """CSV -> {(sexo, obj, peso, bf): {pr_e...gr_d}} con enteros."""
    filas = {}
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            tabla = row["Tabla"]
            sexo = "hombre" if tabla.startswith("Hombre") else "mujer"
            obj = "definicion" if "Defin" in tabla else "volumen"
            key = (sexo, obj, int(float(row["Peso"])), int(float(row["%Grasa"])))
            filas[key] = {c: int(float(row[col])) for c, col in CSV_COLS.items()}
    return filas


def main():
    dry_run = "--dry-run" in sys.argv

    with open(JSON_PATH, encoding="utf-8") as fh:
        actual = json.load(fh)

    v3 = leer_csv()
    print(f"CSV v3: {len(v3)} filas")

    nuevo = {"hombre": [], "mujer": []}
    cambiadas = 0
    conservadas = 0
    for sexo in ("hombre", "mujer"):
        for r in actual[sexo]:
            key = (sexo, r["obj"], int(r["peso"]), int(r["bf"]))
            if key in v3:
                fila = {"peso": int(r["peso"]), "bf": int(r["bf"]), "obj": r["obj"], **v3.pop(key)}
                if any(fila[c] != r[c] for c in CSV_COLS):
                    cambiadas += 1
            else:
                fila = dict(r)  # no viene en v3: se conserva (p.ej. hombre 120 kg bf altos)
                conservadas += 1
            nuevo[sexo].append(fila)

    if v3:
        # Combinaciones nuevas que la tabla actual no tenia
        for (sexo, obj, peso, bf), vals in sorted(v3.items()):
            nuevo[sexo].append({"peso": peso, "bf": bf, "obj": obj, **vals})
        print(f"Filas nuevas (no estaban en la tabla actual): {len(v3)}")

    print(f"Filas actualizadas con valores v3: {cambiadas}")
    print(f"Filas conservadas de la tabla actual (ausentes en v3): {conservadas}")
    print(f"Totales: hombre {len(nuevo['hombre'])}, mujer {len(nuevo['mujer'])}")

    if dry_run:
        print("--dry-run: no se escribe nada")
        return

    shutil.copyfile(JSON_PATH, BACKUP_PATH)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(nuevo, fh, ensure_ascii=False, indent=1)
    print(f"Escrito {JSON_PATH} (backup en {BACKUP_PATH})")


if __name__ == "__main__":
    main()
