"""
El registro de una sesión de entreno hecha (T3 del doc 16-08).

Hasta ahora la app guardaba el PLAN (db.routines: qué le toca) pero no lo HECHO, y por
eso ningún conteo de entrenos era fiable. Esta colección, `workout_logs`, es la fuente
única de "entrenaste 14 de 16 días": la leen la línea de entreno de Inicio (T1), el
Diario (T5), el bloque previo del quincenal (T7) y los datos del mensual (T8).

EL CONTRATO (fijado en la fase 0 para que T1 y T3 avancen en paralelo sin pisarse):

  - `POST /workout-logs` con `WorkoutLogCreate`: upsert por (client_id, fecha). Guardar
    dos veces el mismo día actualiza, no duplica (índice unique en core/database.py).
  - `GET /workout-logs/hoy` -> `{"log": {...} | null}`: lo que Inicio necesita para
    pintar "✓ hecho · ★★★★☆ · Press banca 80 kg" o dejar la línea sin marcar.
  - `GET /workout-logs?desde=YYYY-MM-DD&hasta=YYYY-MM-DD` -> `{"logs": [...]}`: para el
    Diario y los conteos de los reportes.
  - `fecha` es el día DEL CLIENTE, en hora de España (core/tiempo.hoy_madrid), nunca la
    fecha UTC del servidor: a las 23:30 de Madrid el entreno sigue siendo de hoy.
  - `client_id` es el id del PERFIL (client_profiles.id), el mismo criterio que
    `checkins`: en esta base conviven dos ids de cliente y mezclarlos da cifras falsas
    sin error.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class PesoDeReferencia(BaseModel):
    """Una fila de la tabla "Pesos de referencia": ejercicio, reps y el peso de la
    última serie. Se le vuelven a enseñar la próxima vez que le toque esa rutina."""
    ejercicio: str
    reps: Optional[int] = Field(None, ge=0, le=1000)
    peso_kg: Optional[float] = Field(None, ge=0, le=1000)


class WorkoutLogCreate(BaseModel):
    """Lo que manda la pantalla de T3. `fecha` la pone el servidor (hoy en Madrid);
    el cliente no fecha sus entrenos, los registra."""
    hecho: bool
    # "cardio" para los días de solo cardio ("Hoy solo cardio · 40 minutos"): cuentan
    # como día válido en Inicio y como sesión de cardio en el mensual (T8).
    tipo: str = Field("entreno", pattern="^(entreno|cardio)$")
    estrellas: Optional[int] = Field(None, ge=1, le=5)
    nota: Optional[str] = Field(None, max_length=2000)
    pesos: List[PesoDeReferencia] = []
    # La marca del Diario: solo lo compartido lo ve el equipo.
    compartida: bool = False
    # Qué día de la rutina era ("Pierna, abdomen"): lo rellena la pantalla con lo que
    # enseñó, para que la línea de Inicio y el Diario no tengan que recalcularlo.
    dia_rutina: Optional[str] = Field(None, max_length=200)
