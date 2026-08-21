"""
Persistencia del quiz + motor de macros v2 (spec 18-07-2026).

"GUARDAR si o si: todas las respuestas del cuestionario desde el dia uno, se
apliquen o no. Sin esto, en 3 meses no se puede calibrar nada ni entrenar el
modelo predictivo."

- quiz_respuestas: append-only, un doc por cada calculo/envio del quiz.
- macro_revisiones: dieta reportada que no cuadra con lo recomendado; el
  entrenador la revisa (humano en el bucle). Ademas se avisa por la campanita.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from core.database import db


async def guardar_quiz_respuestas(
    user_id: str,
    client_id: Optional[str],
    origen: str,                 # 'quiz_inicial' | 'ajustar_macros' | 'ajustar_macros_guardar' | 'nivel1'
    respuestas: Dict[str, Any],
    resultado: Optional[Dict[str, Any]] = None,
    contexto: Optional[Dict[str, Any]] = None,   # {peso, porcentaje_graso, sexo, objetivo}
) -> None:
    """Registra el envio tal cual. Falla en silencio: guardar el histórico nunca
    debe romper el calculo ni el alta."""
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "client_id": client_id,
            "origen": origen,
            "respuestas": respuestas,
            **(contexto or {}),
            "macros_resultantes": (resultado or {}).get("macros"),
            "desglose": (resultado or {}).get("desglose"),
            "revision": (resultado or {}).get("revision"),
            "no_aplicados": (resultado or {}).get("no_aplicados"),
            "version_motor": (resultado or {}).get("version_motor"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.quiz_respuestas.insert_one(doc)
    except Exception:
        pass


async def registrar_revision(
    profile: Dict[str, Any],
    user: Dict[str, Any],
    resultado: Optional[Dict[str, Any]],
) -> bool:
    """Si la dieta reportada no cuadra (revision.requiere_revision), deja la
    revision pendiente para el coach y le avisa por la campanita. Devuelve si
    se registro revision."""
    revision = (resultado or {}).get("revision") or {}
    if not revision.get("requiere_revision"):
        return False
    try:
        trainer_id = profile.get("trainer_id")
        client_id = profile.get("id")
        # SIN DUPLICADOS. Cada recalculo dejaba un insert, y «Macros por revisar»
        # enseñaba 7 filas del mismo cliente (4 identicas): la lista contaba
        # recalculos, no clientes por revisar. Antes de insertar se cierran las
        # pendientes previas del MISMO cliente, asi que por cliente queda como
        # mucho UNA pendiente y con la comparacion mas reciente.
        filtro = {"client_id": client_id} if client_id else {"user_id": user.get("id")}
        previas = await db.macro_revisiones.update_many(
            {**filtro, "status": "pendiente"},
            {"$set": {"status": "reemplazada",
                      "resolved_at": datetime.now(timezone.utc).isoformat()}},
        )
        await db.macro_revisiones.insert_one({
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "user_id": user.get("id"),
            "trainer_id": trainer_id,
            "comparacion": revision,
            "status": "pendiente",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # La campanita solo la primera vez: si ya habia una pendiente, el aviso ya
        # salio y repetirlo por cada recalculo es ruido, no informacion.
        if trainer_id and previas.modified_count == 0:
            from routes.notifications import notify  # lazy: evita import circular
            nombre = user.get("name") or user.get("email") or "un cliente"
            await notify(
                trainer_id,
                "macros_revision",
                f"Revisar macros de {nombre}: su dieta reportada no cuadra con lo recomendado",
                f"/admin/clients/{client_id}" if client_id else None,
            )
    except Exception:
        pass
    return True
