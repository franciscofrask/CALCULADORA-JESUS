/**
 * LO QUE QUEDÓ DEL VOLCADO DE CALMA NO ES UNA RESPUESTA.
 *
 * «SIN CALIFICAR CUMPLIMIENTO» NO ES UNA RESPUESTA (doc 19-08, apartado 02). Es el valor
 * que Calma deja en el select del cardio cuando el cliente no lo toca -- 91 formularios,
 * sigue pasando en 2026 -- y la ficha lo pintaba como si el cliente lo hubiera dicho:
 * «el cliente pone que no se ha saltado nada y a mí me sale sin calificar el
 * cumplimiento». Si detrás del relleno hay algo escrito por el cliente («Sin calificar
 * cumplimiento. Este mes lo haré 100 %»), eso sí es suyo y eso es lo que se enseña.
 *
 * Y LA BASURA DEL IMPORT TAMPOCO (revisión del 2-09). En los reportes migrados hay campos
 * rellenos con marcas del formulario viejo -- «XX», «xxx», «-», «.», «n/a», «ninguno» --
 * que se pintaban tal cual: el entrenador leía «Problemas para entrenar: XX» y un
 * comentario del cliente que ponía "XX". Medido en producción el 4-09: 27 reportes con
 * «xx» en `problemasParaEntrenar` y uno en `notes`.
 *
 * SE SACÓ AQUÍ EL 4-09 (punto 104 del artefacto «La app, pantalla por pantalla», Gonzalo:
 * «El último reporte de Montalvo, entero, es: XX. Se dio por arreglado que los rellenos ya
 * no se pintaban»). Se había arreglado en el histórico de Seguimiento y en las respuestas
 * de Calma, pero el «Su último reporte» de la pestaña Macros pintaba `notes` en crudo por
 * otro camino. Con la regla en un solo sitio, todo lo que pinte texto de un reporte pasa
 * por aquí y no hay «otro camino».
 */
export const RELLENO_DEL_IMPORT = /^(x+|-+|_+|\.+|n\/?a|na|nada|ninguno?a?|null|none)$/i;

/**
 * El texto si es del cliente; `null` si está vacío o es relleno. Quita por delante el
 * «Sin calificar cumplimiento» del select de Calma y se queda con lo que venga detrás.
 */
export const sinElRelleno = (v) => {
    const limpio = String(v ?? '').replace(/^sin calificar (el )?cumplimiento[.,]?\s*/i, '').trim();
    if (!limpio || RELLENO_DEL_IMPORT.test(limpio)) return null;
    return limpio;
};

/**
 * La nota del reporte, si la escribió el cliente. «Importado de Calma» es la marca que deja
 * la migración en `notes`, y «XX» lo que quedó del volcado: ninguna de las dos se enseña.
 */
export const notaDelCliente = (reporte) => {
    const n = reporte?.notes;
    if (!n || n === 'Importado de Calma') return null;
    return sinElRelleno(n);
};
