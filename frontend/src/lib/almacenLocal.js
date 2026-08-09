/**
 * Lo que la app guarda en el navegador, separado POR CLIENTE. Punto 4.7 de la revisión
 * del 09-08.
 *
 * Lo que pasaba: entras como cliente A, miras el 8 de julio, cierras sesión, entra el
 * cliente B en el mismo navegador y abre Nutrición. Le sale el día de A, con sus alimentos
 * y sus cantidades, y solo cambian los objetivos de macros.
 *
 * La causa era que la copia local del día se guardaba con la fecha como única clave
 * (`nutrition_dia_2026-07-08`), sin nada que dijera de quién es. El primero que la
 * escribiera se la quedaba para todo el que entrara después en ese ordenador.
 *
 * Y NO era solo lo que se veía. Esa copia se sube al servidor: en producción hay dos
 * clientes distintos con exactamente los mismos alimentos guardados el 8 de julio -- 50 g
 * de concentrado de suero, 270 g de pechuga -- y los dos documentos se escribieron el 09-08
 * con cuarenta minutos de diferencia, que es la ventana de la revisión. O sea que la dieta
 * de uno se guardó dentro de la del otro.
 *
 * El servidor está bien: las once consultas a `diets` filtran por `user_id` y ninguna
 * cuenta puede leer la de otra. Era el navegador, y por eso se arregla aquí.
 *
 * Dos redes, porque una sola no basta:
 *
 *   1. La clave lleva dentro el id del cliente, así que dos cuentas no pueden pisarse
 *      aunque la sesión anterior no se cerrase bien (se cierra el portátil y ya).
 *   2. Al cerrar sesión se borra lo que es de esa persona. Lo que es del aparato -- el tema
 *      claro u oscuro, si la barra lateral está plegada -- se queda: no es de nadie.
 */

// Lo que pertenece al APARATO y no a la persona. Sobrevive al cierre de sesión.
const DEL_APARATO = new Set(['token', 'theme', 'sidebar-collapsed']);

// Las que ya se escribieron sin dueño y hay que barrer una vez. Cuando no queden
// navegadores con estas claves puestas, esta lista se puede quitar.
const HUERFANAS = ['nutrition_last_date', 'nutrition_last_date_guardado',
                   'nutrition-intro-seen', 'primera-dieta-hecha',
                   'onboarding-checklist-dismissed'];

/** La clave de `nombre` para este cliente. Sin cliente devuelve null: mejor no guardar
 *  nada que guardarlo donde lo vea el siguiente. */
export const claveDe = (nombre, userId) => (userId ? `u:${userId}:${nombre}` : null);

export const leer = (nombre, userId) => {
    const k = claveDe(nombre, userId);
    if (!k) return null;
    try { return localStorage.getItem(k); } catch { return null; }
};

export const escribir = (nombre, userId, valor) => {
    const k = claveDe(nombre, userId);
    if (!k) return;
    try { localStorage.setItem(k, valor); } catch { /* lleno o bloqueado: no es crítico */ }
};

export const borrar = (nombre, userId) => {
    const k = claveDe(nombre, userId);
    if (!k) return;
    try { localStorage.removeItem(k); } catch { /* nada que hacer */ }
};

/**
 * Borra del navegador todo lo que sea de una persona. Se llama al cerrar sesión.
 *
 * Barre también las claves viejas sin dueño, que son las que causaron el problema y siguen
 * puestas en los navegadores de todo el mundo: si no se limpian, el fallo sobrevive al
 * arreglo hasta que cada uno vacíe su caché.
 */
export const limpiarLoDeLaPersona = () => {
    try {
        const fuera = [];
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (!k) continue;
            if (k.startsWith('u:') || k.startsWith('nutrition_dia_') || HUERFANAS.includes(k)) {
                fuera.push(k);
            }
        }
        fuera.forEach(k => { if (!DEL_APARATO.has(k)) localStorage.removeItem(k); });
    } catch { /* si el navegador no deja tocar el almacen, no se puede hacer mas */ }
};
