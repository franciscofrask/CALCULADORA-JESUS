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
import { num1 } from './numeros';

// EL SUELO DEL «CUADRADO»: MEDIO GRAMO, EL DE CALMA (Francisco, 3-09-2026: «tal cual lo
// hace Calma»). No es una elección nuestra: está en su bundle, en `macros.stepRedondeo = 0.5`,
// y en la función que pinta cada fila -- `Math.round(objetivo − servido) == 0` saca
// «Cuadrado», o sea por debajo de medio gramo; hasta `margenValido = 4`, «Válido»; más allá,
// «faltan» o «sobran». Es la misma escalera que la de abajo.
//
// Estaba en 1 g, que venía de cuando el día iba en enteros y sólo la comida llevaba decimal.
// Con el decimal puesto en todas partes ese suelo SE VE: «249,2 de 250» rotulado «cuadrado»
// vuelve a ser un número que no cuadra con su palabra. Con medio gramo eso se lee
// «válido (−0,8)», que es lo que el cliente tiene delante.
export const SUELO_CUADRADO = 0.5;

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
    // «CUADRADO» ES CUANDO ESTÁ EXACTO (Francisco, 3-09-2026). Esto REVIERTE la revisión
    // del 2-09, que dentro del margen ponía «cuadrado (+2,6)»: «dice cuadrado pero le
    // faltan 2,3; cuadrado es cuando está exacto, si no es válido, o sobra o falta».
    // Es además la letra del punto 11.1 de Jesús: «de 1 a 4, falte o sobre, es VÁLIDO y
    // sale en verde». Así que: exacto -> «cuadrado»; dentro del margen -> «válido» con su
    // desvío, en verde igual; fuera -> «faltan»/«sobran».
    dieta: (estado, desvio, objetivo, n) => {
        if (estado === CLAVADO) return 'cuadrado';
        if (estado === VALIDO) return `válido (${desvio > 0 ? '+' : MENOS}${n(Math.abs(desvio))})`;
        if (estado === PASADO) return `sobran ${n(Math.abs(desvio))}`;
        return `faltan ${n(Math.abs(desvio))}`;
    },
    llevas: (estado, desvio, objetivo, n) => {
        if (estado === PASADO) return `te pasas ${n(Math.abs(desvio))}`;
        // «Ya lo tienes» le dice que puede olvidarse de ése el resto del día, que es lo
        // único que necesita saber en esta pestaña.
        if (estado === CLAVADO || estado === VALIDO) return 'ya lo tienes';
        // Y POR DEBAJO, NADA: el «de 250» ya no vive aquí, vive en `referencia` y se pinta
        // SIEMPRE (ver abajo). Antes esta palabra hacía las dos cosas y por eso el objetivo
        // desaparecía justo cuando aparecía el estado.
        return null;
    },
    falta: (estado, desvio, objetivo, n) => {
        if (estado === PASADO) return `te pasas ${n(Math.abs(desvio))}`;
        // La misma regla del 3-09: «cuadrado» solo el exacto; el del margen, «válido».
        if (estado === CLAVADO) return 'cuadrado';
        if (estado === VALIDO) return 'válido';
        // El número YA es lo que falta, así que no se pone «faltan»: sería decirlo dos veces.
        return 'para llegar';
    },
};
// Dentro de una comida las palabras son las de Dieta -- «cuadrado», «válido (+2,3)»,
// «faltan 4,5» --, lo que cambia es que llevan decimal.
PALABRA.comida = PALABRA.dieta;

/**
 * Lee un macro y devuelve todo lo que hay que pintar de él.
 *
 * @param vista     'macros' | 'dieta' | 'llevas' | 'falta'
 * @param hay       lo que hay YA (lo creado en Dieta, lo comido en Llevas y en Falta)
 * @param objetivo  el total del día para ese macro
 *
 * Los dos entran A LA DÉCIMA, y la palabra se calcula con esos mismos: la regla de siempre
 * («quien escriba una diferencia al lado de dos cifras redondeadas tiene que restar ESAS»),
 * sólo que desde el 3-09 la cifra que se lee lleva decimal en las cuatro pestañas y no sólo
 * dentro de la comida. La palabra tiene que salir de lo que el cliente está leyendo.
 */
export function leerMacro({ vista, hay, objetivo, margen }) {
    if (vista === 'macros') {
        // `apagado` y no `null`: en esta pestaña el número ES el objetivo, así que «tu
        // objetivo» es un rótulo y va en gris. `null` significa otra cosa -- «vas por
        // debajo» --, y eso se pinta en blanco.
        // `referencia: null` explícito y no ausente: quien pinta pregunta por ese campo en
        // las cuatro pestañas, y una forma que a veces trae la clave y a veces no es una
        // trampa esperando. Aquí no hay «de N» porque el número YA es el objetivo.
        return { estado: SIN_ESTADO, palabra: PALABRA.macros(), color: 'apagado',
                 referencia: null, barra: null };
    }
    // EL DECIMAL, TAMBIÉN EN EL GLOBAL (Francisco, 3-09-2026): «que muestre también en el
    // global, así no hay desfase, tal cual lo hace Calma».
    //
    // Esto REVIERTE el punto 80 del 07-08 («ni un decimal en Inicio, ni arriba ni en las
    // comidas»), y con motivo. Con el día redondeado y la comida a la décima, la MISMA comida
    // decía tres cosas a la vez: la fila de Inicio «16G», la tarjeta abierta «15,7» y la
    // plegada «válido +1». Tres cifras del mismo gramo, y el cliente no tiene forma de saber
    // cuál es la buena. Vale más un decimal de más que tres números que no cuadran.
    //
    // Y con el decimal hace falta el mismo SUELO en todas partes, o el día no diría
    // «cuadrado» casi nunca: 249,7 sobre 250 no es un fallo, es que no se puede pesar la
    // diferencia. Así que la regla del gramo, que era de la comida, pasa a ser de la casa.
    const n = num1;
    const meta = objetivo || 0;
    const tiene = hay || 0;
    // Lo que hay MENOS lo que debería haber: negativo es que falta, positivo es que sobra.
    const desvio = tiene - meta;
    const fuera = Math.abs(desvio);
    // El margen puede venir dado; desde el 3-09 (decisión de Francisco: «1-4 plano en
    // todo») `margenDe` devuelve siempre los 4 de Calma, así que dado o no, es el mismo.
    const tope = margen != null ? margen : MARGEN;

    let estado;
    // Clavado: por debajo de medio gramo, en cualquier pantalla. Es el `Math.round(l) == 0`
    // de Calma, y con el decimal delante es lo más ajustado que se puede decir sin mentir.
    if (fuera < SUELO_CUADRADO) estado = CLAVADO;
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
        // EL «DE 250» SE VE SIEMPRE, PASE LO QUE PASE (Francisco, 3-09, con la maqueta del
        // bloque 06 delante: «250 / de 250 / ya lo tienes» y «212 / de 210 / cuadrado
        // (+2)»). Son DOS lineas debajo del numero, no una: arriba contra qué se mide y
        // abajo cómo va.
        //
        // Antes el objetivo y el estado se turnaban en la misma línea, así que el objetivo
        // desaparecía justo cuando el estado tenía algo que decir -- que es cuando más falta
        // hace saber de cuánto hablamos.
        //
        // Solo en Dieta y en Llevas. En Macros el número YA es el objetivo, y en Falta el
        // número es lo que queda: repetir el total ahí no dice nada. Y dentro de una comida
        // tampoco, que ahí la fila ya lleva su objetivo al lado.
        referencia: (vista === 'dieta' || vista === 'llevas') ? `de ${n(meta)}` : null,
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
