/**
 * CÓMO VA UN MACRO Y CÓMO VA EL DÍA: falta, válido o cuadrado.
 *
 * La regla ya existía, pero repartida: `macroState` en las tarjetas de comida
 * (components/nutrition/MealCard.jsx) decide macro a macro, y la cabecera de Nutrición
 * (components/nutrition/DayHeader.jsx, el «Te queda por comer» del móvil) decide el día
 * entero. Inicio necesita las dos para pintar «Te faltan 94 · de 120» con su color y el
 * «Día cuadrado · los tres clavados» de debajo (doc del 16-08, T1), y copiarlas allí
 * habría sido la octava copia del mismo margen.
 *
 * Aquí solo se extrae lo que ya se aplica, sin cambiarlo: el margen es el de `lib/exceso`
 * (los 4 g de Calma) y pasarse solo cuenta como fallo en hidratos y grasa, que es la
 * decisión de Jesús del 13-08. Los tres colores son los del documento: naranja lo que
 * falta, amarillo lo válido, verde lo cuadrado.
 */
import { MARGEN, seExcede } from './exceso';

export const ESTADO = {
    FALTA: 'falta',
    VALIDO: 'valido',
    CUADRADO: 'cuadrado',
    EXCESO: 'exceso',
};

export const COLOR_ESTADO = {
    [ESTADO.FALTA]: '#FF671F',
    [ESTADO.VALIDO]: '#F59E0B',
    [ESTADO.CUADRADO]: '#10B981',
    [ESTADO.EXCESO]: '#EF4444',
};

// La palabra que acompaña al número en Inicio. «Falta» no se dice: ya lo dice el «Te
// faltan 94» de arriba, y repetirlo no añade nada.
export const PALABRA_ESTADO = {
    [ESTADO.VALIDO]: 'válido',
    [ESTADO.CUADRADO]: 'cuadrado',
    [ESTADO.EXCESO]: 'te pasas',
};

/** El estado de UN macro. `key` es 'P', 'H' o 'G': hace falta para saber si pasarse cuenta. */
export function estadoMacro(key, servido, objetivo) {
    const obj = Number(objetivo) || 0;
    const val = Number(servido) || 0;
    // Sin objetivo no hay nada que cuadrar: se trata como pendiente y no se le pone
    // medalla verde a un macro que nadie ha pedido.
    if (obj <= 0) return ESTADO.FALTA;
    const resto = obj - val;
    if (Math.round(resto) === 0) return ESTADO.CUADRADO;
    if (Math.abs(resto) < MARGEN) return ESTADO.VALIDO;
    if (resto > 0) return ESTADO.FALTA;
    // Por arriba: solo hidratos y grasa se marcan; pasarse de proteína no es un fallo.
    return seExcede(key, val, obj) ? ESTADO.EXCESO : ESTADO.CUADRADO;
}

/** Lo que le queda por comer de ese macro, sin negativos: el número grande de Inicio. */
export function faltanDe(servido, objetivo) {
    return Math.max(0, Math.round((Number(objetivo) || 0) - (Number(servido) || 0)));
}

/** Cuánto de la barra va cubierto (0-100). */
export function porcentajeMacro(servido, objetivo) {
    const obj = Number(objetivo) || 0;
    if (obj <= 0) return 0;
    return Math.min(100, Math.max(0, ((Number(servido) || 0) / obj) * 100));
}

/**
 * El estado del DÍA, con `servidos` y `objetivos` en {P, H, G}.
 *
 * Solo hay titular cuando los tres cuadran o los tres están dentro del margen (doc: «Estado
 * del día · solo cuando los tres cuadran o son válidos»). Si a alguno le falta, no se pinta
 * nada: el día todavía no es nada.
 */
export function estadoDelDia(servidos = {}, objetivos = {}) {
    const claves = ['P', 'H', 'G'];
    if (!claves.some((k) => (Number(objetivos[k]) || 0) > 0)) return null;
    const estados = claves.map((k) => estadoMacro(k, servidos[k], objetivos[k]));
    if (estados.every((e) => e === ESTADO.CUADRADO)) return ESTADO.CUADRADO;
    if (estados.every((e) => e === ESTADO.CUADRADO || e === ESTADO.VALIDO)) return ESTADO.VALIDO;
    return null;
}

export const TEXTO_ESTADO_DIA = {
    [ESTADO.CUADRADO]: 'Día cuadrado · los tres clavados',
    [ESTADO.VALIDO]: 'Día válido · los tres dentro del margen',
};

/**
 * UNA DE LAS VARIANTES, Y NUNCA LA MISMA DOS DÍAS SEGUIDOS (regla 6 del doc: «cada aviso
 * con 2 o 3 textos que rotan»).
 *
 * En el backend esto lo hace `variante_para()` mirando lo último que se le mandó. Aquí no
 * hay nada que mirar -- el cierre de Inicio no se guarda en ningún sitio --, así que la
 * rotación va por día y por cliente: dentro del mismo día siempre sale la misma frase (si
 * no, cambiaría al recargar) y al día siguiente sale otra.
 */
export function varianteDelDia(variantes, semilla = '') {
    const lista = variantes || [];
    if (!lista.length) return '';
    const hoy = new Date();
    const dias = Math.floor(Date.UTC(hoy.getFullYear(), hoy.getMonth(), hoy.getDate()) / 86400000);
    let h = dias;
    for (const c of String(semilla)) h = (h * 31 + c.charCodeAt(0)) % 1000003;
    return lista[Math.abs(h) % lista.length];
}
