import urllib.request
import json
import sys

API_KEY = "AIzaSyCDeFM3SpZBxrAFQzhnZkm5LtnREjg_KTs"
PROJECT = "jesusgallegopt"
DATABASE = "calma-alimentos"
COLLECTION = "alimentos_aprobados"
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/{DATABASE}/documents/{COLLECTION}"

def get_value(field):
    if field is None:
        return None
    for vtype in ['stringValue', 'integerValue', 'doubleValue', 'booleanValue', 'nullValue']:
        if vtype in field:
            val = field[vtype]
            if vtype == 'integerValue':
                return int(val)
            return val
    if 'arrayValue' in field:
        vals = field['arrayValue'].get('values', [])
        return [get_value(v) for v in vals]
    return None

all_docs = []
page_token = None
page = 0

while True:
    url = f"{BASE_URL}?key={API_KEY}&pageSize=300"
    if page_token:
        url += f"&pageToken={page_token}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    docs = data.get('documents', [])
    all_docs.extend(docs)
    page += 1
    print(f"Page {page}: {len(docs)} docs, total {len(all_docs)}")
    page_token = data.get('nextPageToken')
    if not page_token:
        break

alimentos = []
for doc in all_docs:
    f = doc.get('fields', {})
    alimento_id = get_value(f.get('alimentoId'))
    nombre = get_value(f.get('nombre'))
    categorias_arr = get_value(f.get('categorias')) or []
    racion = get_value(f.get('racion')) or 100
    proteinas = get_value(f.get('proteinas')) or 0
    hidratos = get_value(f.get('hidratos')) or 0
    grasas = get_value(f.get('grasas')) or 0
    url = get_value(f.get('url'))
    unidades = get_value(f.get('unidades')) or False
    minimo_raw = f.get('minimo')
    minimo = None
    if minimo_raw and 'nullValue' not in minimo_raw:
        minimo = get_value(minimo_raw)
    foto_frente = get_value(f.get('fotoFrente'))
    foto_reverso = get_value(f.get('fotoReverso'))
    categorias_str = ' | '.join(str(c) for c in categorias_arr if c is not None)
    a = {
        'id': alimento_id,
        'nombre': nombre,
        'categorias': categorias_str,
        'racion': racion,
        'proteinas': float(proteinas),
        'hidratos': float(hidratos),
        'grasas': float(grasas),
        'unidades': unidades,
    }
    if url:
        a['url'] = url
    if minimo is not None:
        a['minimo'] = float(minimo)
    if foto_frente:
        a['foto_frente'] = foto_frente
    if foto_reverso:
        a['foto_reverso'] = foto_reverso
    alimentos.append(a)

alimentos.sort(key=lambda x: x.get('id') or 0)

out_path = 'alimentos_calma.json'
with open(out_path, 'w', encoding='utf-8') as out:
    json.dump(alimentos, out, ensure_ascii=False, indent=2)

print(f"\nTOTAL: {len(alimentos)} alimentos -> {out_path}")
