# -*- coding: utf-8 -*-
"""Lo que falto en cada punto, para poder decidir si es un fallo o un dato de la maqueta."""
import io
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = json.load(io.open(os.path.join(RAIZ, "_guia", "_capturas", "_manifiesto.json"),
                      encoding="utf-8"))
for x in m:
    if x["estado"] == "completo":
        continue
    print(f'[{x["estado"]:8}] {x["escena_id"]} · {x["titulo"]}')
    for f in x["faltan"]:
        print(f'      x {f[:100]}')
