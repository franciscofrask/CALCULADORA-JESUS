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
 * NARANJA SOLO PARA LO QUE SE PASA. Del 26-08 al 27-08 esto pintó naranja también lo que
 * faltaba -- decisión de Francisco, «a partir de 5, falte o sobre» --, y el 27-08 vuelve a la
 * frase de arriba: manda la maqueta de la parte 6, que dibuja un día a medias y lo remata con
 * «ni un color en toda la pantalla, porque no hay nada mal, sólo cosas por hacer».
 *
 * O sea tres estados y no dos: verde resuelto, naranja pasado, y SIN COLOR por debajo. Ir
 * corto no es un error, es que todavía no has terminado, y el naranja pintaba de aviso la
 * pantalla entera de cualquiera que abriera la app por la mañana.
 *
 * Lo que distingue faltar de sobrar sigue siendo la LONGITUD de la barra: la del que falta
 * está corta y la del que sobra está llena a tope (punto 83). Ahora, además, el color.
 */
import { MARGEN } from './exceso';
import { num0, num1 } from './numeros';

// DENTRO DE UNA COMIDA SÍ VAN DECIMALES (puntos 121 y 122 del artifact del 26-08): «es la
// pantalla donde se afina. En el resto de la app, redondos». Y con el decimal hace falta un
// suelo, porque si no la palabra se pone a cantar medios gramos: «medio gramo de grasa no lo
// pesa nadie, y no se pueden cortar 0,2 g de una nuez». Por debajo de 1 g, cuadrado.
export const SUELO_DE_LA_COMIDA = 1;

/**
 * LOS CUATRO COLORES, en un solo sitio para que las dos pantallas que leen esto pinten igual.
 *
 *   'ok'        verde     ese macro ya está resuelto
 *   'pasado'    naranja   te has pasado
 *   null        blanco    vas por debajo: no es un error, es que no has terminado
 *   'apagado'   gris      no es un estado (el rótulo «tu objetivo» de la pestaña Macros)
 */
export const claseDelMacro = (color) => (
    color === 'ok' ? 'text-ok font-medium'
    : color === 'pasado' ? 'text-pasado font-medium'
    : color === 'apagado' ? 'text-muted-foreground'
    : 'text-foreground');

//: El relleno de la barra. Por debajo va en gris: la barra dice cuánto llevas, no si vas mal.
export const fondoDelMacro = (color) => (
    color === 'ok' ? 'bg-ok'
    : color === 'pasado' ? 'bg-pasado'
    : 'bg-muted-foreground/40');

//: Y el punto solo lo llevan los dos que son un estado de verdad.
export const llevaPunto = (color) => color === 'ok' || color === 'pasado';

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
    dieta: (estado, desvio, objetivo, n) => {
        if (estado === CLAVADO) return 'cuadrado';
        if (estado === VALIDO) return `válido ${desvio > 0 ? '+' : MENOS}${n(Math.abs(desvio))}`;
        if (estado === PASADO) return `sobran ${n(Math.abs(desvio))}`;
        return `faltan ${n(Math.abs(desvio))}`;
    },
    llevas: (estado, desvio, objetivo, n) => {
        if (estado === PASADO) return `te pasas ${n(Math.abs(desvio))}`;
        // «Ya lo tienes» le dice que puede olvidarse de ése el resto del día, que es lo
        // único que necesita saber en esta pestaña.
        if (estado === CLAVADO || estado === VALIDO) return 'ya lo tienes';
        return `de ${n(objetivo)}`;
    },
    falta: (estado, desvio, objetivo, n) => {
        if (estado === PASADO) return `te pasas ${n(Math.abs(desvio))}`;
        if (estado === CLAVADO || estado === VALIDO) return 'cuadrado';
        // El número YA es lo que falta, así que no se pone «faltan»: sería decirlo dos veces.
        return 'para llegar';
    },
};
// Dentro de una comida las palabras son las de Dieta -- «cuadrado», «válido +2,3»,
// «faltan 4,5» --, lo que cambia es que llevan decimal.
PALABRA.comida = PALABRA.dieta;

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
export function leerMacro({ vista, hay, objetivo, margen }) {
    if (vista === 'macros') {
        // `apagado` y no `null`: en esta pestaña el número ES el objetivo, así que «tu
        // objetivo» es un rótulo y va en gris. `null` significa otra cosa -- «vas por
        // debajo» --, y eso se pinta en blanco.
        return { estado: SIN_ESTADO, palabra: PALABRA.macros(), color: 'apagado', barra: null };
    }
    // DENTRO DE UNA COMIDA NO SE REDONDEA, ni el número ni la palabra (punto 121). En el
    // resto de la app sí: un decimal en un total del día no decide nada y ensucia.
    const conDecimales = vista === 'comida';
    const n = conDecimales ? num1 : num0;
    const meta = conDecimales ? (objetivo || 0) : Math.round(objetivo || 0);
    const tiene = conDecimales ? (hay || 0) : Math.round(hay || 0);
    // Lo que hay MENOS lo que debería haber: negativo es que falta, positivo es que sobra.
    const desvio = tiene - meta;
    const fuera = Math.abs(desvio);
    // El margen puede venir dado: dentro de una comida es el proporcional de `lib/exceso`
    // (`margenDe`), porque 4 g sobre los 9 de proteína de un intra son casi la mitad.
    const tope = margen != null ? margen : MARGEN;

    let estado;
    // Clavado: exacto en el resto de la app; por debajo de 1 g dentro de una comida.
    if (conDecimales ? fuera < SUELO_DE_LA_COMIDA : desvio === 0) estado = CLAVADO;
    else if (fuera <= tope) estado = VALIDO;
    else if (desvio > 0) estado = PASADO;
    else estado = CORTO;

    const resuelto = estado === CLAVADO || estado === VALIDO;
    // Verde dentro del margen, naranja al pasarse, y NADA por debajo: los tres estados de la
    // frase de arriba. `null` es «vas por debajo», y quien pinta decide qué hacer con él (el
    // número en blanco y la barra en gris).
    const color = resuelto ? 'ok' : estado === PASADO ? 'pasado' : null;
    return {
        estado,
        desvio,
        palabra: (PALABRA[vista] || PALABRA.dieta)(estado, desvio, meta, n),
        color,
        barra: {
            // La barra hace algo que el punto no hace: en un día cuadrado se llenan las
            // tres de verde de lado a lado. Y su LONGITUD es lo que distingue faltar de
            // sobrar: la del que falta está corta, la del que sobra está llena a tope.
            largo: resuelto || estado === PASADO
                ? 100
                : (meta > 0 ? Math.max(0, Math.min(100, (tiene / meta) * 100)) : 0),
            color,
        },
    };
}
