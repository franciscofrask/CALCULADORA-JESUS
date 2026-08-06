/**
 * Cómo se escribe un precio.
 *
 * El documento de Jesús del 06-08-2026 lo escribe "1.500 €" en las tres pantallas donde
 * sale el Nivel 3: el test, planes y la renovación.
 *
 * Y aquí hay una trampa que costó encontrar: `(1500).toLocaleString('es-ES')` devuelve
 * "1500", SIN punto, y no es un fallo. La convención española no agrupa los números de
 * cuatro cifras (por eso un año se escribe 1500 y no 1.500), y los datos de idioma la
 * aplican. Para un precio se quiere el punto igualmente, así que el separador se pone
 * aquí a mano en vez de confiar en el idioma del navegador.
 *
 * El valor no se toca: el catálogo manda (1500). Esto es solo cómo se pinta.
 */

// 1500 -> "1.500" · 297 -> "297" · 1499.5 -> "1.499,5" · 12345 -> "12.345"
export const formatEuros = (n) => {
    const num = Number(n || 0);
    const signo = num < 0 ? '-' : '';
    // Como mucho dos decimales, y sin arrastrar ceros: 297.00 -> "297", 1499.50 -> "1.499,5"
    const [entera, decimal] = Math.abs(num).toFixed(2).replace(/0+$/, '').replace(/\.$/, '').split('.');
    const conMillares = entera.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return signo + conMillares + (decimal ? `,${decimal}` : '');
};

// 1500 -> "1.500 €"
export const euros = (n) => `${formatEuros(n)} €`;

// Lo mismo para cualquier otro número que se enseñe (el contador de personas: 1.325).
// Existe para no volver a tirar de toLocaleString y quedarse otra vez sin el punto.
export const numero = formatEuros;
