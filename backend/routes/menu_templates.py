"""
CRUD de plantillas de menú (los menús preestablecidos de "Sugiéreme un menú").
Gestionable por admin y coaches (get_admin_user). Se guardan en db.menu_templates.
La primera lectura siembra la colección desde las PLANTILLAS hardcodeadas.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends

from core.database import db
from core.security import get_admin_user
from meal_templates import load_menu_templates
from calculator import get_categoria_principal

router = APIRouter(prefix="/admin/menu-templates", tags=["menu-templates"])

MOMENTOS = {"desayuno", "comida", "merienda", "cena"}
ROLES = {"proteina", "hidrato", "grasa"}  # el método solo usa estos 3 macros


async def _clean_and_validate(data: dict) -> dict:
    """Valida y normaliza una plantilla de menú. Lanza HTTPException(400) si algo falla.
    Si un item trae `alimento_id` (del buscador), resuelve su nombre y categoría reales."""
    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(400, "El nombre es obligatorio")

    momento = (data.get("momento") or "").strip().lower()
    if momento not in MOMENTOS:
        raise HTTPException(400, f"Momento inválido. Usa: {', '.join(sorted(MOMENTOS))}")

    # El rango de kcal ya no se edita (era la 'calorías'); se deja ABIERTO para que el menú
    # sea candidato en cualquier tamaño de comida (el ajuste y el orden por cercanía deciden).
    try:
        min_kcal = float(data.get("min_kcal") or 0)
        max_kcal = float(data.get("max_kcal") or 0)
    except (TypeError, ValueError):
        min_kcal, max_kcal = 0.0, 0.0
    if max_kcal <= 0:
        max_kcal = 99999.0
    if min_kcal < 0 or min_kcal > max_kcal:
        min_kcal = 0.0

    items_in = data.get("items") or []
    if not isinstance(items_in, list) or not items_in:
        raise HTTPException(400, "El menú debe tener al menos un alimento (item)")
    items = []
    for i, it in enumerate(items_in):
        if not isinstance(it, dict):
            raise HTTPException(400, f"Item {i + 1} inválido")
        rol = (it.get("rol") or "").strip().lower()
        if rol not in ROLES:
            raise HTTPException(400, f"Item {i + 1}: rol inválido. Usa: {', '.join(sorted(ROLES))}")
        buscar = (it.get("buscar") or "").strip()
        categoria = str(it.get("categoria") or "").strip()
        # Si viene un alimento concreto (del buscador), resolvemos su nombre y categoría reales.
        alimento_id = it.get("alimento_id")
        if alimento_id not in (None, ""):
            try:
                alimento_id = int(alimento_id)
            except (TypeError, ValueError):
                raise HTTPException(400, f"Item {i + 1}: alimento_id inválido")
            food = await db.foods.find_one({"id": alimento_id}, {"_id": 0})
            if not food:
                raise HTTPException(400, f"Item {i + 1}: alimento no encontrado (id {alimento_id})")
            buscar = food.get("nombre", buscar)
            categoria = get_categoria_principal(food) or categoria
        else:
            alimento_id = None
        if not buscar:
            raise HTTPException(400, f"Item {i + 1}: falta el alimento")
        prop = it.get("proporcion")
        if isinstance(prop, str):
            prop = prop.strip().lower()
            if prop != "ajuste":
                try:
                    prop = float(prop)
                except ValueError:
                    raise HTTPException(400, f"Item {i + 1}: proporción inválida (número o 'ajuste')")
        elif prop is None:
            prop = 1.0
        else:
            try:
                prop = float(prop)
            except (TypeError, ValueError):
                raise HTTPException(400, f"Item {i + 1}: proporción inválida")
        item = {"rol": rol, "buscar": buscar, "categoria": categoria, "proporcion": prop}
        if alimento_id is not None:
            item["alimento_id"] = alimento_id
        items.append(item)

    tags = data.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()]

    return {
        "nombre": nombre, "momento": momento,
        "min_kcal": min_kcal, "max_kcal": max_kcal,
        "tags": tags, "items": items,
    }


@router.get("")
async def list_templates(momento: str = None, user=Depends(get_admin_user)):
    """Lista todas las plantillas (opcionalmente filtradas por momento)."""
    await load_menu_templates(db)  # asegura que estén sembradas
    q = {}
    if momento:
        q["momento"] = momento.strip().lower()
    docs = await db.menu_templates.find(q, {"_id": 0}).to_list(2000)
    docs.sort(key=lambda d: (d.get("momento", ""), d.get("id", "")))
    return {"templates": docs, "total": len(docs)}


async def _enrich_macros(items: list) -> list:
    """Añade a cada item sus macros por 100 g (guía visual del editor). Resuelve por
    alimento_id o, si no, por nombre+categoría (los 60 originales)."""
    from meal_templates import _buscar_alimento_generico
    out = []
    for it in items:
        food = None
        if it.get("alimento_id") not in (None, ""):
            food = await db.foods.find_one({"id": int(it["alimento_id"])}, {"_id": 0})
        if not food and it.get("buscar"):
            food = await _buscar_alimento_generico(db, it["buscar"], it.get("categoria", ""))
        macros = None
        if food:
            macros = {
                "P": round(float(food.get("proteinas") or 0)),
                "H": round(float(food.get("hidratos") or 0)),
                "G": round(float(food.get("grasas") or 0)),
            }
        out.append({**it, "macros": macros})
    return out


@router.get("/{template_id}")
async def get_template(template_id: str, user=Depends(get_admin_user)):
    doc = await db.menu_templates.find_one({"id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Menú no encontrado")
    doc["items"] = await _enrich_macros(doc.get("items", []))
    return doc


@router.post("")
async def create_template(data: dict, user=Depends(get_admin_user)):
    """Crea un menú nuevo, que se añade al listado existente."""
    await load_menu_templates(db)  # asegura sembrado antes de crear
    clean = await _clean_and_validate(data)
    new_id = "M" + uuid.uuid4().hex[:8].upper()
    while await db.menu_templates.count_documents({"id": new_id}):
        new_id = "M" + uuid.uuid4().hex[:8].upper()
    doc = {
        "id": new_id, **clean,
        "origen": "custom",
        "created_by": user.get("email") or user.get("id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.menu_templates.insert_one(dict(doc))
    return doc


@router.put("/{template_id}")
async def update_template(template_id: str, data: dict, user=Depends(get_admin_user)):
    """Edita un menú existente (de los 60 sembrados o de los creados)."""
    clean = await _clean_and_validate(data)
    clean["updated_by"] = user.get("email") or user.get("id")
    clean["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.menu_templates.update_one({"id": template_id}, {"$set": clean})
    if result.matched_count == 0:
        raise HTTPException(404, "Menú no encontrado")
    return await db.menu_templates.find_one({"id": template_id}, {"_id": 0})


@router.delete("/{template_id}")
async def delete_template(template_id: str, user=Depends(get_admin_user)):
    result = await db.menu_templates.delete_one({"id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Menú no encontrado")
    return {"deleted": template_id}
