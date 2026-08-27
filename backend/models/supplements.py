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
    # CON QUE COMIDA SALE EN EL INICIO (punto 174 del 27-08). Vacio = que lo deduzca del
    # `cuando`; ver core/comida_del_suplemento. Valores: "" | primera | ultima | C1..C4 |
    # ninguna. Se elige UNA vez aqui y vale para todos los clientes.
    comida: str = ""


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
    # Lo mismo que en la ficha del catalogo, pero para ESTE cliente: si a uno le toca en otra
    # comida, se le cambia aqui sin mover la ficha de los demas. Vacio = manda la ficha, y si
    # la ficha tampoco dice nada, el `cuando`.
    comida: str = ""
    # DONDE SALE, YA RESUELTO. Lo calcula el servidor al servir el protocolo (no se guarda):
    # una lista de huecos, «primera» y «ultima» en simbolico porque el numero de comidas del
    # dia lo sabe la pantalla y no el protocolo. Lista vacia = no sale en ninguna comida.
    en_comidas: List[str] = []


class VersionProtocolo(BaseModel):
    """El protocolo que el cliente toma DESDE una fecha (punto 33 del 07-08).

    El protocolo se guarda como una lista de versiones con fecha y se resuelve por la mas
    reciente que no pase de hoy, igual que los macros. Eso da las tres cosas que faltaban:
    se puede editar, queda el registro de que tomaba en cada momento, y se puede dejar uno
    preparado para el futuro (una version con fecha de la semana que viene).

    `items` es una LISTA DE VERDAD, no "3|7|12" en un texto: cada suplemento con su dosis,
    su momento y sus observaciones, editables aunque venga del catalogo.
    """
    fecha: str                                     # "YYYY-MM-DD": desde cuando aplica
    items: List[ProtocolItem] = []
    nota: Optional[str] = None
    guardado_por: Optional[str] = None
    guardado_at: Optional[str] = None


class SupplementProtocolSave(BaseModel):
    actual: List[ProtocolItem] = []
    # Desde cuando aplica el bloque "actual". Si no viene, se respeta la fecha de la version
    # vigente (editar no inventa una version nueva) y si no habia ninguna, hoy.
    actual_fecha: Optional[str] = None             # "YYYY-MM-DD"
    siguiente: List[ProtocolItem] = []
    siguiente_fecha: Optional[str] = None          # "YYYY-MM-DD"
    nota: Optional[str] = None


class SupplementProtocolResponse(SupplementProtocolSave):
    client_id: str
    updated_at: Optional[str] = None
    # El historico completo. `actual` y `siguiente` salen de aqui, resueltos por fecha.
    versiones: List[VersionProtocolo] = []
    # `actual` NO es lo que le ha pautado el coach, sino la suplementacion general, la que
    # se ensena mientras no tenga la suya (peticion de Jesus del 18-08). Quien lo consuma
    # tiene que poder distinguirlo: la pantalla lo dice con otras palabras y en Inicio no
    # se ensena, porque alli "Tu suplementacion" significa la que le tocan a el.
    es_generica: bool = False
