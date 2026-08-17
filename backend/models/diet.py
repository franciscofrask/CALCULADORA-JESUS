"""
Modelos Pydantic para dietas y alimentos.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, List, Any

# Diet Models
class DietFood(BaseModel):
    id: Optional[int] = None
    nombre: str
    cantidad: float
    unidad: str = "g"
    macros: Dict[str, float]

class DietMeal(BaseModel):
    alimentos: List[DietFood] = []
    macros: Dict[str, float] = {"P": 0, "H": 0, "G": 0}

class DietSave(BaseModel):
    fecha: str
    config: Dict[str, Any]
    meals: Dict[str, DietMeal]

class DietResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    fecha: str
    config: Dict[str, Any]
    meals: Dict[str, Any]
    created_at: str
    updated_at: str

# Chatbot Models
class ChatConfigRequest(BaseModel):
    tipo_dia: str
    num_comidas: int = 4
    momento_entreno: int = 1
    opcion_peri: str = "intra_post"
    single_meal: bool = False
    # Qué fecha se está montando: el asistente la necesita para resolver "mañana" o "el
    # jueves" contra el día que el cliente tiene abierto, no contra hoy.
    fecha: Optional[str] = None
    # ¿Tiene que saludar la respuesta? El chat arranca solo con la configuración de
    # Nutrición y es el front quien la cuenta ("Vamos con Hoy, con lo que tienes en
    # Nutrición: ..."); si además la repite esta ruta, parece que el asistente se contesta
    # a sí mismo (17-08-2026). El front manda False; por defecto se saluda.
    saludo: bool = True

class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

class ChatCompleteMealRequest(BaseModel):
    session_id: str
