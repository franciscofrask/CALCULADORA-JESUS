"""
Modelos de la sección de Suplementación.

Espejo del patrón de rutinas: catálogo editable por el entrenador +
protocolo asignado por cliente (actual / siguiente + fecha + nota).
"""
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid


# ── Catálogo (CRUD admin) ────────────────────────────────────────────────
class SupplementCatalogItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    titulo: str                                   # nombre visible (ej: "Monohidrato de creatina")
    imagen: Optional[str] = None                  # URL de imagen
    enlaces: List[str] = []                        # enlaces de compra
    cuando: str = ""                               # timing (texto): "Todos los días, con el desayuno"
    cuanto: str = ""                               # dosis (texto): "10 g" / "la cantidad que cuadre tus macros"
    observaciones: Optional[str] = None            # notas (puede llevar HTML simple)
    sexo: str = "ambos"                            # "hombre" | "mujer" | "ambos"
    categoria: str = "base"                        # base | quemador | rendimiento | salud | sueno | intra | otro
    objetivo: str = "ambos"                         # "volumen" | "definicion" | "ambos"
    orden: int = 0
    activo: bool = True


# ── Protocolo asignado por cliente ──────────────────────────────────────
class ProtocolItem(BaseModel):
    """Snapshot editable de un suplemento dentro del protocolo del cliente."""
    catalog_id: Optional[str] = None
    titulo: str
    imagen: Optional[str] = None
    enlaces: List[str] = []
    cuando: str = ""
    cuanto: str = ""
    observaciones: Optional[str] = None


class SupplementProtocolSave(BaseModel):
    actual: List[ProtocolItem] = []
    siguiente: List[ProtocolItem] = []
    siguiente_fecha: Optional[str] = None          # "YYYY-MM-DD"
    nota: Optional[str] = None


class SupplementProtocolResponse(SupplementProtocolSave):
    client_id: str
    updated_at: Optional[str] = None
