/**
 * MODO REVISIÓN: abrir cualquier pantalla en el estado que hace falta ver.
 *
 * Hay pantallas de la app a las que no se puede llegar cuando uno quiere, porque dependen de
 * los datos del cliente: el formulario del reporte solo se abre de viernes a lunes y solo la
 * semana que le toca, la de «suscripción caducada» solo la ve quien se ha quedado sin plan, y
 * el cuestionario del alta no se puede repetir una vez hecho. Eso está bien para el cliente,
 * pero deja al equipo sin forma de revisarlas: para ver el reporte mensual había que esperar
 * al fin de semana bueno, y para ver la de caducado, caducarle el plan a alguien.
 *
 * Con `?ver=` en la dirección, la pantalla se pinta en el estado que se le pida. Reglas:
 *
 *   - SOLO PARA EL EQUIPO. Un cliente que se invente el parámetro no ve nada distinto.
 *   - NO TOCA NINGÚN DATO. Es la misma pantalla con otro estado de partida; lo que se envíe
 *     desde ella pasa por las mismas comprobaciones del servidor, que no sabe nada de esto.
 *     O sea: se puede MIRAR el reporte fuera de plazo, pero no colarlo.
 *
 * Las direcciones están en el documento del circuito, que es donde se consultan.
 */

const EQUIPO = new Set(['admin', 'trainer']);

export function verComo(user) {
    if (!user || !EQUIPO.has(user.role)) return null;
    try {
        return new URLSearchParams(window.location.search).get('ver') || null;
    } catch {
        return null;   // navegador raro o sin URL: como si no se hubiera pedido
    }
}

export default verComo;
