/**
 * La revisión suelta de macros, en el lado del cliente.
 *
 * Documento de Jesús del 06-08-2026: se ofrece en dos momentos y de una sola forma.
 *
 *   - NUNCA como popup. "Un popup interrumpe, y esto no puede interrumpir: si aparece
 *     encima de lo que está haciendo, es publicidad aunque el texto sea suave". Va como
 *     una línea pequeña, sin botón grande, y de ahí se entra a la pantalla (/revision).
 *   - Momento 1: al recibir sus macros de inicio, el primer día. Es la revisión DE PARTIDA.
 *   - Momento 2: al recibir su ajuste del mes. Es la revisión PERSONALIZADA.
 *   - A los Niveles 2 y 3 no se les muestra nunca: ya la tienen incluida.
 *
 * El precio de verdad lo pone el backend al cobrar (core/revision_suelta.PRECIO_EUR);
 * esto es solo para escribirlo en pantalla.
 */
export const PRECIO_REVISION = 147;

/**
 * ¿Se le ofrece? Solo a quien no tiene entrenador detrás (el Nivel 1) y no tiene ya una
 * revisión en marcha o hecha.
 *
 * @param {object} profile  perfil del cliente
 * @param {function} can    la capacidad del plan (useAuth().can)
 */
export function seLeOfreceLaRevision(profile, can) {
    if (!profile) return false;
    if (can && can('macros_personalizados')) return false;   // Niveles 2 y 3: la llevan dentro
    return !profile?.revision_suelta?.estado;
}
