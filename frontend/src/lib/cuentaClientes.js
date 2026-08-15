/**
 * CUÁNTOS CLIENTES HAY: UN SOLO CRITERIO (#56 del informe del 15-08).
 *
 * «Dashboard: 178 clientes totales. Clientes: 180 CLIENTES. Su propia pestaña: Todos (182)».
 * Tres números para lo mismo, y ninguno mentía: cada pantalla contaba una cosa distinta sin
 * decir cuál.
 *
 *   - 178 es lo que cuenta el servidor en `dashboard-stats`: fichas de cliente, sin el
 *     equipo.
 *   - 182 son las filas que devuelve `/admin/clients?include_incomplete=true`, que añade a
 *     los que se registraron y no llegaron a elegir plan (no tienen ficha) y, desde el
 *     13-08, la ficha del propio miembro del equipo que esté mirando.
 *   - 180 era el subtítulo «CLIENTES», que contaba las filas de la pestaña abierta -- «Sin
 *     entrenador» -- pero se leía como el total.
 *
 * El criterio bueno ya existía y es el del servidor; lo que faltaba era que la tabla contara
 * igual. Aquí vive esa regla, y la usan el listado y sus pestañas. Si algún día cambia,
 * cambia en un sitio.
 */

// Una fila de `/admin/clients` que cuenta como cliente del negocio.
export const cuentaComoCliente = (c) =>
    !!c && c.status !== 'registro_incompleto' && !c.es_tu_ficha;

export const contarClientes = (filas) => (filas || []).filter(cuentaComoCliente).length;

// Los que se registraron y no terminaron: se enseñan igual -- son trabajo -- pero no son
// clientes y por eso van contados aparte en vez de sumarse al total.
export const contarRegistrosSinTerminar = (filas) =>
    (filas || []).filter(c => c?.status === 'registro_incompleto').length;
