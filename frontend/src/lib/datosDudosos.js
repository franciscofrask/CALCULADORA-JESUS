/**
 * La frase de los macros provisionales, CON el dato que falta (punto 24 del doc del
 * 23-08: «el cliente pincha, se encuentra un formulario largo y no sabe qué rellenar»).
 *
 * `datos_dudosos` viene del servidor (core/datos_dudosos.py) con el nombre humano de
 * cada campo: aquí solo se redacta. Dos motivos, dos tramos de frase:
 *   falta      → «nos falta tu altura y tu objetivo»
 *   imposible  → «revisa tu edad: el valor guardado no puede ser»
 */
const juntar = (nombres) => (nombres.length === 1
    ? nombres[0]
    : `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}`);

export const fraseDeLoQueFalta = (dudosos) => {
    const faltan = (dudosos || []).filter(d => d.motivo === 'falta').map(d => `tu ${d.nombre}`);
    const malos = (dudosos || []).filter(d => d.motivo === 'imposible').map(d => `tu ${d.nombre}`);
    const partes = [];
    if (faltan.length) partes.push(`nos falta ${juntar(faltan)}`);
    if (malos.length) partes.push(`revisa ${juntar(malos)}: el valor guardado no puede ser`);
    if (!partes.length) return 'Para poder darte tus macros definitivos necesitas completar tus datos.';
    const frase = partes.join(' y ');
    return `Para darte tus macros definitivos ${frase}.`;
};

export default fraseDeLoQueFalta;
