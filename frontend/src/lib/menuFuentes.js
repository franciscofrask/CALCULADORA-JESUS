/**
 * De dónde salen los menús que ofrece la app.
 *
 * Dos fuentes, y no valen lo mismo:
 *   - Recetario: las 103 recetas de "No te conformes con menos", con nombre, receta
 *     y foto. Es material terminado de Jesús y va primero.
 *   - Biblioteca: comidas reales sacadas de las dietas de los clientes. Son de
 *     relleno, no tienen nombre ni foto, y van detrás.
 *
 * La biblioteca estuvo apagada del 06-08 al 08-08-2026, y con razón: se ofrecían los
 * 266.170 en crudo y salían batidos y listas de botes. Se enciende ahora porque ya
 * pasan el filtro de calidad del punto 67 (que lleven verdura, que no vayan cargados
 * de suplementos, que tengan un número razonable de ingredientes) y porque se ordenan
 * por cuánta GENTE DISTINTA los ha montado. De 23.681 quedan 1.946 comidas de plato.
 *
 * Para apagarlos otra vez: poner esto en false y BIBLIOTECA_DE_CLIENTES en
 * backend/meal_library.py también. Las dos, o el front pedirá menús que el backend
 * no sirve.
 */
export const BIBLIOTECA_DE_CLIENTES = true;
