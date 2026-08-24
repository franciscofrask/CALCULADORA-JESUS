"""¿Cuándo se le ajustaron los macros por última vez?

EL DESFASE (caso «el último ajuste del panel es el del histórico», rojo desde el 19-08 y
medido el 23-08): el panel leía `client_profiles.ultimo_ajuste`, un campo que escribe
`marcar_ajuste` cuando el ajuste pasa por la pestaña de Macros. La migración de Calma
mete filas en `macro_history` con un `insert_many` (`_sync_macros_peso.py`) y NO llama a
`marcar_ajuste`, así que el campo se queda en la fecha vieja: medidos 37 clientes en dev
con el panel por detrás de su propio histórico (uno decía «1 de junio» con 44 ajustes y
el último del 17 de agosto).

LA REGLA, con las dos trampas que aparecieron al medir:

  1. Se corta en HOY. Hay una fila con `effective_date` de 2029 (un dedazo al fechar un
     ajuste): tomar el máximo a secas la habría dado por «ajustado hoy» y ese cliente
     habría desaparecido de «esta semana te tocan» hasta 2029.

  2. Sin filas en el histórico manda el campo. Hay clientes migrados cuyo ajuste vive en
     `calma_raw.macros_historial` y nunca llegó a `macro_history` (de ahí el script
     `_rellenar_fechas_seguimiento.py`): derivar a pelo los convertiría en «nunca
     ajustado» y los pondría los primeros de la lista del lunes, que es justo el fallo
     que aquel script vino a arreglar.

Así que se toma LO MÁS RECIENTE de las dos fuentes sin pasar de hoy y, si ninguna vale
(campo con fecha futura y sin histórico), se devuelve lo que hubiera: nadie se convierte
en «nunca ajustado» por un arreglo de pantalla.

Se resuelve en UNA consulta para toda la lista: el panel carga 3.000 perfiles y no puede
preguntar por cada uno.
"""
from typing import Dict, Iterable, Optional

from core.tiempo import hoy_madrid


async def ultimos_ajustes_vigentes(db, client_ids: Iterable[str],
                                   hoy: Optional[str] = None) -> Dict[str, str]:
    """{client_id: 'AAAA-MM-DD'} con la última fila del histórico que ya está vigente."""
    ids = [c for c in client_ids if c]
    if not ids:
        return {}
    dia = hoy or hoy_madrid().isoformat()
    filas = await db.macro_history.aggregate([
        # La fecha buena es `effective_date`, NUNCA `created_at`: en las filas migradas
        # `created_at` es el día de la migración (trampa conocida de la casa).
        {"$match": {"client_id": {"$in": ids}, "effective_date": {"$lte": dia}}},
        {"$group": {"_id": "$client_id", "ultimo": {"$max": "$effective_date"}}},
    ]).to_list(len(ids))
    return {f["_id"]: f["ultimo"] for f in filas if f.get("ultimo")}


def ajuste_de(perfil: dict, derivados: Dict[str, str], hoy: Optional[str] = None) -> Optional[str]:
    """La fecha que se enseña de ese cliente. Ver la explicación de arriba."""
    dia = hoy or hoy_madrid().isoformat()
    guardado = str(perfil.get("ultimo_ajuste") or "")[:10] or None
    derivado = derivados.get(perfil.get("id"))
    validos = [f for f in (guardado, derivado) if f and f <= dia]
    if validos:
        return max(validos)
    return guardado or derivado
