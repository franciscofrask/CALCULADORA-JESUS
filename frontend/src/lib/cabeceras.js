/**
 * LAS CABECERAS DE UNA PETICIÓN, EN UN SOLO SITIO.
 *
 * Por qué existe esto (17-08-2026, punto 2 del documento de Jesús).
 *
 * Cuando el entrenador entra en la calculadora de un cliente, la app manda
 * `X-Actuar-Como: <user_id>` y el backend resuelve al cliente ahí (ver
 * `core/actuar_como.py`). Esa cabecera la ponía SOLO el cliente axios de
 * `AuthContext`. Pero Nutrición y el asistente no lo usan: cada uno se había
 * montado su propio `fetch` con el token a mano -- uno en Nutrición y dieciséis
 * llamadas sueltas en el asistente -- y ninguno la mandaba.
 *
 * El resultado, medido en producción antes de arreglarlo: al entrar en la
 * calculadora de Cliente Demo, `POST /calculator/distribute` devolvía los macros
 * del ADMIN (200/80/50 en vez de 210/170/50), y `GET /diets/2026-07-05` devolvía
 * el día del admin -- doce alimentos en día de entreno -- mientras el cliente
 * tenía tres en día de descanso. Y lo que se guardara desde ahí se guardaba en la
 * cuenta del admin, encima de su propio día, bajo el cartel «Estás en la cuenta
 * de Cliente Demo».
 *
 * La lección es la de siempre en este proyecto: dos caminos para lo mismo y uno
 * peor. Mientras existan helpers propios, que al menos las cabeceras salgan de
 * aquí, para que añadir una tercera no vuelva a ser «acuérdate de tocar diecisiete
 * sitios».
 */

/** El id del cliente al que se está suplantando, o null. Vive en sessionStorage
 *  a propósito: se acaba al cerrar la pestaña (ver AuthContext). */
export function actuandoComoId() {
    try {
        const crudo = sessionStorage.getItem('actuar_como');
        if (!crudo) return null;
        return JSON.parse(crudo)?.userId || null;
    } catch {
        return null;   // sessionStorage capado o JSON roto: como si no se actuara como nadie
    }
}

/**
 * Las cabeceras de autenticación de una petición.
 *
 * @param {string} token          el JWT
 * @param {object} extra          cabeceras propias de la llamada (Content-Type...)
 */
export function cabeceras(token, extra = {}) {
    const id = actuandoComoId();
    return {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(id ? { 'X-Actuar-Como': id } : {}),
        ...extra,
    };
}

export default cabeceras;
