"""La traza de cada turno del asistente, guardada donde no se la lleve un despliegue.

POR QUÉ EXISTE ESTO
-------------------
La traza (qué herramientas llamó el agente, con qué argumentos y qué le devolvieron) se
escribía solo con `logger.info` en el pod. Eso vive lo que viva el proceso: el despliegue
del 17-08 se llevó por delante todas las del día anterior, justo las de la sesión que
había que analizar. Y lo único que se guardaba en la base era `chatbot_sessions`, que
tiene el ESTADO (la comida en curso, los borradores), no lo que pasó.

Resultado: ante un «¿por qué me ha puesto un litro de leche?» solo se podía contestar
mirando el resultado y deduciendo. Con esto se puede leer el turno entero: el mensaje del
cliente, lo que llamó el agente en orden, lo que le contestó cada herramienta y lo que
acabó diciéndole.

DECISIONES
----------
**Caduca a los 30 días.** Es un registro de diagnóstico, no un archivo: al mes ya no sirve
para nada y sí ocuparía. Mismo mecanismo que las sesiones (índice TTL), con más margen
porque un fallo se reporta días después de ocurrir.

**Se guarda TODO turno, también los atajos.** El agente tiene una docena de caminos que
contestan antes de llegar al modelo (el «sí» a una oferta, deshacer, navegar). Justo esos
son los que más confunden cuando algo sale raro, porque no dejan traza de herramientas: el
documento dirá `herramientas: []` y eso ya es la respuesta.

**Con los tiempos dentro.** Cuánto tardó el turno y cuánto se fue en herramientas. La
diferencia es el modelo. Sin esto, «el chat va lento» no se puede ni medir ni desmentir.

**Nunca rompe el chat.** Falla en silencio, como los avisos: quedarse sin registro es un
problema nuestro, no del cliente que está montando su comida.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import db

logger = logging.getLogger(__name__)

DIAS_QUE_SE_GUARDA = 30

# Topes de lo que se escribe. Un turno con quince búsquedas y sus resultados completos son
# cientos de kilobytes; para diagnosticar basta con el principio de cada cosa.
TOPE_MENSAJE = 1500
TOPE_RESPUESTA = 4000
TOPE_ARGS = 400
TOPE_RESUMEN = 300
TOPE_LLAMADAS = 40


def _corta(valor: Any, tope: int) -> Any:
    texto = valor if isinstance(valor, str) else str(valor)
    return texto if len(texto) <= tope else texto[:tope] + "…"


def _llamadas(traza: Optional[List[dict]]) -> List[dict]:
    import json

    fuera = []
    for t in (traza or [])[:TOPE_LLAMADAS]:
        try:
            args = json.dumps(t.get("args"), ensure_ascii=False)
        except Exception:
            args = str(t.get("args"))
        fuera.append({
            "herramienta": t.get("herramienta"),
            "args": _corta(args, TOPE_ARGS),
            "resultado": _corta(t.get("resultado_resumen") or "", TOPE_RESUMEN),
            "ms": t.get("ms"),
        })
    return fuera


def _restante(chatbot) -> Optional[dict]:
    try:
        return chatbot.get_remaining_macros()
    except Exception:
        return None


async def guardar(*, chatbot, mensaje: str, respuesta: Optional[dict],
                  ms: int, error: Optional[str] = None) -> None:
    """Escribe el turno. No levanta nunca: si esto falla, el cliente no se entera."""
    try:
        respuesta = respuesta or {}
        estado = getattr(chatbot, "state", {}) or {}
        llamadas = _llamadas(respuesta.get("traza"))
        ms_herramientas = sum(int(l["ms"]) for l in llamadas if isinstance(l.get("ms"), int))

        doc: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "session_id": getattr(chatbot, "session_id", None),
            "user_id": getattr(chatbot, "usuario_id", None),
            # El día de la dieta sobre el que estaba trabajando, que no tiene por qué ser
            # hoy: el agente puede estar montando el de mañana.
            "fecha_dieta": estado.get("fecha") or estado.get("fecha_dieta"),
            "comida": estado.get("comida_actual"),
            "paso": estado.get("step"),
            "mensaje": _corta(mensaje or "", TOPE_MENSAJE),
            "respuesta": _corta(respuesta.get("message") or "", TOPE_RESPUESTA),
            "herramientas": llamadas,
            "sin_herramientas": not llamadas,
            "ms_total": int(ms),
            "ms_herramientas": ms_herramientas,
            # Lo que quedaba de la comida al terminar: con esto se ve si el turno la dejó
            # cuadrada, corta o pasada sin tener que reconstruir los macros a mano. Se lee
            # del propio bot y no de la respuesta, porque ese cálculo lo arma la ruta
            # DESPUÉS de pasar por aquí (`_estado_para_front`).
            "restante": _restante(chatbot),
            "error": error,
            "created_at": datetime.now(timezone.utc),
        }
        await db.chat_traces.insert_one(doc)
    except Exception:
        logger.warning("no se pudo guardar la traza del chat", exc_info=True)
