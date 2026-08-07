/**
 * Las diez medidas de Jesús. Las suyas, todas, siempre.
 *
 * "Las medidas se tienen que pedir las que he pedido siempre. Sirvan o no, se piden
 * siempre" (06-08-2026). Antes se pedían cinco, y solo la cintura era obligatoria: el
 * resto iba plegado detrás de un "añadir el resto (opcional)".
 *
 * POR QUÉ IMPORTA QUE ESTÉN TODAS Y SIEMPRE: el motivo de que no se fíe de las medidas es
 * que cada mes se mide de una forma distinta. Con el vídeo y la instrucción delante, el
 * error al menos se repite, y lo que interesa no es que el número sea exacto sino que se
 * pueda comparar con el del mes pasado.
 */

export const MEDIDAS = [
    { key: 'hombros', label: 'Hombros' },
    { key: 'mesoesternal', label: 'Mesoesternal' },
    { key: 'brazo_d', label: 'Brazo derecho relajado' },
    { key: 'brazo_i', label: 'Brazo izquierdo relajado' },
    { key: 'muslo_d', label: 'Muslo derecho' },
    { key: 'muslo_i', label: 'Muslo izquierdo' },
    { key: 'cadera', label: 'Cadera' },
    { key: 'cintura', label: 'Cintura' },
    { key: 'gemelo_d', label: 'Gemelo derecho' },
    { key: 'gemelo_i', label: 'Gemelo izquierdo' },
];

/**
 * Las que se guardaron con los nombres viejos, para que el "mes pasado" no salga vacío
 * en el primer reporte con las diez.
 *
 * Solo se traducen las que son LA MISMA medida: la cintura y la cadera. El "pecho" viejo
 * NO se da por mesoesternal, ni el "brazo" por el derecho, porque no se sabe cómo se
 * tomaron y compararlos daría saltos que no ha dado el cliente. En esas, el mes pasado
 * aparece en blanco hasta que haya un dato nuevo, que es lo honesto.
 */
const EQUIVALENTES = { cintura: 'waist', cadera: 'hip' };

// El valor del mes pasado para una medida, mirando también el nombre viejo.
export const valorAnterior = (medidas, key) => {
    if (!medidas) return null;
    const v = medidas[key];
    if (v != null && v !== '') return Number(v);
    const viejo = EQUIVALENTES[key];
    if (viejo && medidas[viejo] != null && medidas[viejo] !== '') return Number(medidas[viejo]);
    return null;
};

// La diferencia con el mes pasado, ya formateada: "+1,5" / "-0,5" / null si no procede.
export const diferencia = (ahora, antes) => {
    const a = parseFloat(ahora);
    if (isNaN(a) || antes == null) return null;
    const d = Math.round((a - antes) * 10) / 10;
    if (d === 0) return { texto: 'igual', signo: 0 };
    return { texto: `${d > 0 ? '+' : ''}${String(d).replace('.', ',')}`, signo: Math.sign(d) };
};

// Cómo medir los perímetros. Va incrustado arriba del bloque y siempre visible: es lo
// único que hace que el error se repita igual todos los meses.
export const VIDEO_MEDIDAS = 'https://player.vimeo.com/video/796836155?h=e1436af05e';
