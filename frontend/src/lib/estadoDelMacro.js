/**
 * CÓMO VA UN MACRO EN EL INICIO: la regla de color, en un solo sitio.
 *
 * Del artifact del 25-08 (puntos 78, 79, 82 y 83), y la frase que lo resume es suya:
 * «verde si ese macro ya está resuelto · naranja si te has pasado · sin color mientras
 * vas por debajo. Igual en las cuatro pestañas, sin excepciones».
 *
 * Antes cada pestaña se lo apañaba por su cuenta dentro del JSX: solo Falta pintaba algo,
 * solo cuando el número salía negativo, y no había margen ninguno -- un gramo de desvío ya
 * cambiaba el color. Ahora las cuatro preguntan aquí.
 *
 * EL MARGEN SON 4 g, PLANOS. Se usa `MARGEN` de `lib/exceso`, que es el de Calma y el que
 * ya aplican las comidas, pero NO su `margenDe()`: aquel estrecha el margen cuando lo que
 * se pide es poco (9 g de proteína en el intra) y aquí hablamos siempre de los totales del
 * día, que son cientos de gramos. «De 1 a 4, falte o sobre, es válido y sale en verde. A
 * partir de 5, naranja. No hace falta cuadrar al gramo.»
 *
 * POR DEBAJO NUNCA PINTA. Ni corto de 5 ni corto de 200: mientras vas por debajo no hay
 * nada que corregir, solo día por delante. El naranja es solo para lo que se ha pasado, y
 * por eso no hace falta leyenda: sin punto significa que no hay nada que mirar.
 */
import { MARGEN } from './exceso';

export const SIN_ESTADO = 'sin_estado';
export const CORTO = 'corto';
export const VALIDO = 'valido';
export const CLAVADO = 'clavado';
export const PASADO = 'pasado';

// El signo de «válido +3» / «válido −4» es el MENOS de verdad (U+2212), no un guion: al
// lado de un número, el guion se lee como parte del texto y el menos se lee como signo.
const MENOS = '−';

const PALABRA = {
    // Macros no lleva estado NUNCA: ahí el número es el objetivo, no hay bueno ni malo.
    macros: () => 'tu objetivo',
    dieta: (estado, desvio) => {
        if (estado === CLAVADO) return 'cuadrado';
        if (estado === VALIDO) return `válido ${desvio > 0 ? '+' : MENOS}${Math.abs(desvio)}`;
        if (estado === PASADO) return `sobran ${Math.abs(desvio)}`;
        return `faltan ${Math.abs(desvio)}`;
    },
    llevas: (estado, desvio, objetivo) => {
        if (estado === PASADO) return `te pasas ${Math.abs(desvio)}`;
        // «Ya lo tienes» le dice que puede olvidarse de ése el resto del día, que es lo
        // único que necesita saber en esta pestaña.
        if (estado === CLAVADO || estado === VALIDO) return 'ya lo tienes';
        return `de ${objetivo}`;
    },
    falta: (estado, desvio) => {
        if (estado === PASADO) return `te pasas ${Math.abs(desvio)}`;
        if (estado === CLAVADO || estado === VALIDO) return 'cuadrado';
        // El número YA es lo que falta, así que no se pone «faltan»: sería decirlo dos veces.
        return 'para llegar';
    },
};

/**
 * Lee un macro y devuelve todo lo que hay que pintar de él.
 *
 * @param vista     'macros' | 'dieta' | 'llevas' | 'falta'
 * @param hay       lo que hay YA (lo creado en Dieta, lo comido en Llevas y en Falta)
 * @param objetivo  el total del día para ese macro
 *
 * Los dos entran REDONDEADOS (punto 80): si la palabra se calculara con decimales, diría
 * «válido −4» debajo de un número que ya se ve clavado, y el cliente creería que la app
 * miente. La palabra tiene que salir de lo mismo que él está leyendo.
 */
export function leerMacro({ vista, hay, objetivo }) {
    if (vista === 'macros') {
        return { estado: SIN_ESTADO, palabra: PALABRA.macros(), color: null, barra: null };
    }
    const meta = Math.round(objetivo || 0);
    const tiene = Math.round(hay || 0);
    // Lo que hay MENOS lo que debería haber: negativo es que falta, positivo es que sobra.
    const desvio = tiene - meta;

    let estado;
    if (desvio === 0) estado = CLAVADO;
    else if (Math.abs(desvio) <= MARGEN) estado = VALIDO;
    else if (desvio > 0) estado = PASADO;
    else estado = CORTO;

    const resuelto = estado === CLAVADO || estado === VALIDO;
    return {
        estado,
        desvio,
        palabra: (PALABRA[vista] || PALABRA.dieta)(estado, desvio, meta),
        // El punto y la palabra: verde si está resuelto, naranja si se ha pasado, y nada
        // mientras va por debajo.
        color: resuelto ? 'ok' : (estado === PASADO ? 'pasado' : null),
        barra: {
            // La barra hace algo que el punto no hace: en un día cuadrado se llenan las
            // tres de verde de lado a lado. Y su LONGITUD distingue faltar de sobrar sin
            // gastar color: la del que falta está corta, la del que sobra está llena.
            largo: resuelto || estado === PASADO
                ? 100
                : (meta > 0 ? Math.max(0, Math.min(100, (tiene / meta) * 100)) : 0),
            color: resuelto ? 'ok' : (estado === PASADO ? 'pasado' : null),
        },
    };
}
