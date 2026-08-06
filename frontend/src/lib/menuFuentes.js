/**
 * De dónde salen los menús que ofrece la app.
 *
 * Había dos fuentes:
 *   - Recetario: las 99 recetas de "No te conformes con menos", con nombre y receta.
 *   - Biblioteca: 266.170 comidas reales sacadas de las dietas de los clientes.
 *
 * Decisión del 06-08-2026 (Francisco): fuera la biblioteca de clientes, solo el
 * recetario. Los datos NO se han borrado -- siguen en db.meal_library, con copia en
 * _internos_proceso/meal_library_backup_0608.jsonl.gz -- solo se ha dejado de mirar.
 *
 * Para volver atrás: poner esto en true y BIBLIOTECA_DE_CLIENTES en
 * backend/meal_library.py también. Las dos, o el front pedirá menús que el backend
 * ya no sirve.
 */
export const BIBLIOTECA_DE_CLIENTES = false;
